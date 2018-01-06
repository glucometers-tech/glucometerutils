# -*- coding: utf-8 -*-
"""Driver for LifeScan OneTouch Verio IQ devices.

Currently work in progress, untested.

Expected device path: /dev/ttyUSB0 or similar serial port device. Device should
be auto-detected if not provided.
"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2018, Diego Elio Pettenò'
__license__ = 'MIT'

import binascii
import datetime
import logging

import construct

from glucometerutils import common
from glucometerutils.support import construct_extras
from glucometerutils.support import lifescan
from glucometerutils.support import lifescan_binary_protocol
from glucometerutils.support import serial

_PACKET = lifescan_binary_protocol.LifeScanPacket(
    0x03, True)

_VERSION_REQUEST = construct.Const(b'\x0d\x01')

_VERSION_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'version' / construct.PascalString(construct.Byte, encoding='ascii'),
    # NULL-termination is not included in string length.
    construct.Constant('\x00'),
)

_SERIAL_NUMBER_REQUEST = construct.Const(
    b'\x0b\x01\x02')

_SERIAL_NUMBER_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'serial_number' / construct.CString(encoding='ascii'),
)

_READ_RTC_REQUEST = construct.Const(b'\x20\x02')

_READ_RTC_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,
)

_WRITE_RTC_REQUEST = construct.Struct(
    construct.Const(b'\x20\x01'),
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,
)

_GLUCOSE_UNIT_REQUEST = construct.Const(
    b'\x09\x02\x02')


_GLUCOSE_UNIT_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'unit' / lifescan_binary_protocol.GLUCOSE_UNIT,
    construct.Padding(3),
)

_MEMORY_ERASE_REQUEST = construct.Const(b'\x1a')  # Untested

_READ_RECORD_COUNT_REQUEST = construct.Const(b'\x27\x00')

_READ_RECORD_COUNT_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'count' / construct.Int16ul,
)

_READ_RECORD_REQUEST = construct.Struct(
    construct.Const(b'\x21'),
    'record_id' / construct.Int16ul,
)

_READING_RESPONSE = construct.Struct(
    lifescan_binary_protocol.COMMAND_SUCCESS,
    'timestamp' / construct_extras.Timestamp(construct.Int32ul),
    'value' / construct.Int32ul,
    'control' / construct.Byte,  # Unknown value
)


class Device(serial.SerialDevice):
    BAUDRATE = 9600
    DEFAULT_CABLE_ID = '10c4:85a7'  # Specific ID for embedded cp210x
    TIMEOUT = 0.5

    def __init__(self, device):
        super(Device, self).__init__(device)
        self.buffered_reader_ = construct.Rebuffered(
            lifescan_binary_protocol.PACKET, tailcutoff=1024)

    def connect(self):
        pass

    def disconnect(self):
        pass

    def _send_packet(self, message):
        pkt = lifescan_binary_protocol.PACKET.build(
            {'value': {
                'message': request,
                'link_control': {},  # Verio does not use link_control.
            }})
        logging.debug('sending packet: %s', binascii.hexlify(pkt))

        self.serial_.write(pkt)
        self.serial_.flush()

    def _read_packet(self):
        raw_pkt = self.buffered_reader_.parse_stream(self.serial_)
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
            _READ_RTC_REQUEST, _READ_RTC_RESPONSE)

        return response.timestamp

    def set_datetime(self, date=datetime.datetime.now()):
        response = self._send_request(
            _WRITE_RTC_REQUEST, {
                'timestamp': date,
            }, _READ_RTC_RESPONSE)

        return response.timestamp

    def zero_log(self):
        self._send_request(
            _MEMORY_ERASE_REQUEST, None,
            lifescan_binary_protocol.COMMAND_SUCCESS)

    def get_glucose_unit(self):
        response = self._send_request(
            _GLUCOSE_UNIT_REQUEST, None, _GLUCOSE_UNIT_RESPONSE)

        return response.unit

    def _get_reading_count(self):
        response = self._send_request(
            _READ_RECORD_REQUEST, {'record_id': _INVALID_RECORD},
            _READING_COUNT_RESPONSE)
        return response.count

    def _get_reading(self, record_id):
        response = self._send_request(
            _READ_RECORD_REQUEST, {'record_id': record_id}, _READING_RESPONSE)

        return common.GlucoseReading(
            response.timestamp, float(response.value))

    def get_readings(self):
        record_count = self._get_reading_count()
        for record_id in range(record_count):
            yield self._get_reading(record_id)
