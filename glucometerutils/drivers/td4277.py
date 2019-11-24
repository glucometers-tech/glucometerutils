# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for TaiDoc TD-4277 devices.

Supported features:
    - get readings, including pre-/post-meal notes;
    - get and set date and time;
    - get serial number (partial);
    - memory reset (caution!)

Expected device path: 0001:001c:00 (libusb), /dev/hidraw1 (Linux).
"""

import binascii
import datetime
import enum
import functools
import logging
import operator

import construct

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import serial

class Direction(enum.Enum):
    In = 0xa5
    Out = 0xa3


def byte_checksum(data):
    return functools.reduce(operator.add, data) & 0xFF


_PACKET = construct.Struct(
    'data' / construct.RawCopy(
        construct.Struct(
            construct.Const(b'\x51'),
            'command' / construct.Byte,
            'message' / construct.Bytes(4),
            'direction' / construct.Mapping(
                construct.Byte,
                {e: e.value for e in Direction}),
        ),
    ),
    'checksum' / construct.Checksum(
        construct.Byte, byte_checksum, construct.this.data.data),
)

_EMPTY_MESSAGE = 0

_CONNECT_REQUEST = 0x22
_VALID_CONNECT_RESPONSE = {0x22, 0x24, 0x54}

_GET_DATETIME = 0x23
_SET_DATETIME = 0x33

_GET_MODEL = 0x24

_GET_READING_COUNT = 0x2b
_GET_READING_DATETIME = 0x25
_GET_READING_VALUE = 0x26

_CLEAR_MEMORY = 0x52

_MODEL_STRUCT = construct.Struct(
    construct.Const(b'\x77\x42'),
    construct.Byte,
    construct.Byte,
)

_DATETIME_STRUCT = construct.Struct(
    'day' / construct.Int16ul,
    'minute' / construct.Byte,
    'hour' / construct.Byte,
)

_DAY_BITSTRUCT = construct.BitStruct(
    'year' / construct.BitsInteger(7),
    'month' / construct.BitsInteger(4),
    'day' / construct.BitsInteger(5),
)

_READING_COUNT_STRUCT = construct.Struct(
    'count' / construct.Int16ul,
    construct.Int16ul,
)

_READING_SELECTION_STRUCT = construct.Struct(
    'record_id' / construct.Int16ul,
    construct.Const(b'\x00\x00'),
)

_MEAL_FLAG = {
    common.Meal.NONE: 0x00,
    common.Meal.BEFORE: 0x40,
    common.Meal.AFTER: 0x80,
}

_READING_VALUE_STRUCT = construct.Struct(
    'value' / construct.Int16ul,
    construct.Const(b'\x06'),
    'meal'/ construct.Mapping(
        construct.Byte, _MEAL_FLAG),
)

def _make_packet(command, message, direction=Direction.Out):
    return _PACKET.build(
        {'data': {
            'value': {
                'command': command,
                'message': message,
                'direction': direction,
            },
        }})


def _parse_datetime(message):
    date = _DATETIME_STRUCT.parse(message)
    # We can't parse the day properly with a single pass of Construct
    # unfortunately.
    day = _DAY_BITSTRUCT.parse(construct.Int16ub.build(date.day))
    return datetime.datetime(
        2000+day.year, day.month, day.day, date.hour, date.minute)


def _select_record(record_id):
    return _READING_SELECTION_STRUCT.build({'record_id': record_id})


class Device(serial.SerialDevice):
    BAUDRATE = 19200
    TIMEOUT = 0.5

    def __init__(self, device):
        super(Device, self).__init__('cp2110://' + device)
        self.buffered_reader_ = construct.Rebuffered(
            _PACKET, tailcutoff=1024)

    def _send_command(
            self, command, message=_EMPTY_MESSAGE, validate_response=True):
        pkt = _make_packet(command, message)
        logging.debug('sending packet: %s', binascii.hexlify(pkt))

        self.serial_.write(pkt)
        self.serial_.flush()
        response = self.buffered_reader_.parse_stream(self.serial_)
        logging.debug('received packet: %r', response)

        if validate_response and response.data.value.command != command:
            raise InvalidResponse(response)

        return response.data.value.command, response.data.value.message

    def connect(self):
        response_command, message = self._send_command(
            _CONNECT_REQUEST, validate_response=False)
        if response_command not in _VALID_CONNECT_RESPONSE:
            raise exceptions.ConnectionFailed(
                'Invalid response received: %2x %r' % (
                    response_command, message))

        _, model_message = self._send_command(_GET_MODEL)
        try:
            _MODEL_STRUCT.parse(model_message)
        except construct.ConstructError:
            raise exceptions.ConnectionFailed(
                'Invalid model identified: %r' % model_message)

    def disconnect(self):
        pass

    def get_meter_info(self):
        return common.MeterInfo('TaiDoc TD-4277 glucometer')

    def get_version(self):  # pylint: disable=no-self-use
        raise NotImplementedError

    def get_serial_number(self):  # pylint: disable=no-self-use
        raise NotImplementedError

    def get_datetime(self):
        _, message = self._send_command(_GET_DATETIME)

        return _parse_datetime(message)

    def set_datetime(self, date=datetime.datetime.now()):
        assert date.year >= 2000

        day_struct = _DAY_BITSTRUCT.build({
            'year': date.year - 2000,
            'month': date.month,
            'day': date.day,
        })

        day_word = construct.Int16ub.parse(day_struct)

        date_message = _DATETIME_STRUCT.build({
            'day': day_word,
            'minute': date.minute,
            'hour': date.hour})

        _, message = self._send_command(_SET_DATETIME, message=date_message)

        return _parse_datetime(message)

    def _get_reading_count(self):
        _, message = self._send_command(_GET_READING_COUNT)

        return _READING_COUNT_STRUCT.parse(message).count

    def _get_reading(self, record_id):
        _, reading_date_message = self._send_command(
            _GET_READING_DATETIME,
            _select_record(record_id))
        reading_date = _parse_datetime(reading_date_message)

        _, reading_value_message = self._send_command(
            _GET_READING_VALUE,
            _select_record(record_id))
        reading_value = _READING_VALUE_STRUCT.parse(reading_value_message)

        return common.GlucoseReading(
            reading_date, reading_value.value, meal=reading_value.meal)

    def get_readings(self):
        record_count = self._get_reading_count()
        for record_id in range(record_count):
            yield self._get_reading(record_id)

    def zero_log(self):
        self._send_command(_CLEAR_MEMORY)
