# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for LifeScan OneTouch Verio IQ devices.

Supported features:
    - get readings, including pre-/post-meal notes;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/ttyUSB0 or similar serial port device. Device will be
auto-detected.

"""

import binascii
import datetime
import logging

import construct

from glucometerutils import common
from glucometerutils.support import construct_extras
from glucometerutils.support import lifescan
from glucometerutils.support import lifescan_binary_protocol
from glucometerutils.support import serial

_PACKET = lifescan_binary_protocol.LifeScanPacket(False)

_COMMAND_SUCCESS = construct.Const(b'\x03\x06')

_VERSION_REQUEST = construct.Const(b'\x03\x0d\x01')

_VERSION_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'version' / construct.PascalString(construct.Byte, encoding='ascii'),
    # NULL-termination is not included in string length.
    construct.Const(b'\x00'),
)

_SERIAL_NUMBER_REQUEST = construct.Const(
    b'\x03\x0b\x01\x02')

_SERIAL_NUMBER_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'serial_number' / construct.CString(encoding='ascii'),
)

_READ_RTC_REQUEST = construct.Const(b'\x03\x20\x02')

_READ_RTC_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
)

_WRITE_RTC_REQUEST = construct.Struct(
    construct.Const(b'\x03\x20\x01'),
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
)

_GLUCOSE_UNIT_REQUEST = construct.Const(
    b'\x03\x09\x02\x02')


_GLUCOSE_UNIT_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'unit' / lifescan_binary_protocol.GLUCOSE_UNIT,
    construct.Padding(3),
)

_MEMORY_ERASE_REQUEST = construct.Const(b'\x03\x1a')

_READ_RECORD_COUNT_REQUEST = construct.Const(b'\x03\x27\x00')

_READ_RECORD_COUNT_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'count' / construct.Int16ul,
)

_READ_RECORD_REQUEST = construct.Struct(
    construct.Const(b'\x03\x21'),
    'record_id' / construct.Int16ul,
)

_MEAL_FLAG = {
    common.Meal.NONE: 0x00,
    common.Meal.BEFORE: 0x01,
    common.Meal.AFTER: 0x02,
}

_READING_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
    'value' / construct.Int16ul,
    'control_test' / construct.Flag,
    'meal' / construct.Mapping(
        construct.Byte, _MEAL_FLAG),
    construct.Padding(2),  # unknown
)


class Device(serial.SerialDevice):
    BAUDRATE = 38400
    DEFAULT_CABLE_ID = '10c4:85a7'  # Specific ID for embedded cp210x
    TIMEOUT = 0.5

    def __init__(self, device):
        super(Device, self).__init__(device)
        self.buffered_reader_ = construct.Rebuffered(_PACKET, tailcutoff=1024)

    def connect(self):
        pass

    def disconnect(self):
        pass

    def _send_packet(self, message):
        pkt = _PACKET.build(
            {'data': {'value': {
                'message': message,
            }}})
        logging.debug('sending packet: %s', binascii.hexlify(pkt))

        self.serial_.write(pkt)
        self.serial_.flush()

    def _read_packet(self):
        raw_pkt = self.buffered_reader_.parse_stream(self.serial_).data
        logging.debug('received packet: %r', raw_pkt)

        # discard the checksum and copy
        pkt = raw_pkt.value

        return pkt

    def _send_request(self, request_format, request_obj, response_format):
        try:
            request = request_format.build(request_obj)
            self._send_packet(request)

            response_pkt = self._read_packet()

            return response_format.parse(response_pkt.message)
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def get_meter_info(self):
        return common.MeterInfo(
            'OneTouch Verio IQ glucometer',
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self.get_version(),),
            native_unit=self.get_glucose_unit())

    def get_version(self):
        response = self._send_request(
            _VERSION_REQUEST, None, _VERSION_RESPONSE)

        return response.version

    def get_serial_number(self):
        response = self._send_request(
            _SERIAL_NUMBER_REQUEST, None, _SERIAL_NUMBER_RESPONSE)

        return response.serial_number

    def get_datetime(self):
        response = self._send_request(
            _READ_RTC_REQUEST, None, _READ_RTC_RESPONSE)

        return response.timestamp

    def set_datetime(self, date=datetime.datetime.now()):
        self._send_request(
            _WRITE_RTC_REQUEST, {
                'timestamp': date,
            }, _COMMAND_SUCCESS)

        # The device does not return the new datetime, so confirm by calling
        # READ RTC again.
        return self.get_datetime()

    def zero_log(self):
        self._send_request(
            _MEMORY_ERASE_REQUEST, None,
            _COMMAND_SUCCESS)

    def get_glucose_unit(self):
        response = self._send_request(
            _GLUCOSE_UNIT_REQUEST, None, _GLUCOSE_UNIT_RESPONSE)

        return response.unit

    def _get_reading_count(self):
        response = self._send_request(
            _READ_RECORD_COUNT_REQUEST, None, _READ_RECORD_COUNT_RESPONSE)
        return response.count

    def _get_reading(self, record_id):
        response = self._send_request(
            _READ_RECORD_REQUEST, {'record_id': record_id}, _READING_RESPONSE)

        if response.control_test:
            logging.debug('control solution test, ignoring.')
            return None

        return common.GlucoseReading(
            response.timestamp, float(response.value), meal=response.meal)

    def get_readings(self):
        record_count = self._get_reading_count()
        for record_id in range(record_count):
            reading = self._get_reading(record_id)
            if reading:
                yield reading
