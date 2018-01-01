# -*- coding: utf-8 -*-
"""Driver for LifeScan OneTouch Ultra Easy devices.

Also supports OneTouch Ultra Mini devices (different name, same device).

Supported features:
    - get readings;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/ttyUSB0 or similar serial port device.
"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2014-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import binascii
import datetime
import logging

import construct

from glucometerutils import common
from glucometerutils.support import construct_extras
from glucometerutils.support import lifescan
from glucometerutils.support import serial


_INVALID_RECORD = 501


_PACKET = construct.Struct(
    construct.RawCopy(
        construct.Embedded(
            construct.Struct(
                construct.Const(b'\x02'),  # stx
                'length' / construct.Rebuild(
                    construct.Byte, lambda ctx: len(ctx.message) + 6),
                construct.EmbeddedBitStruct(
                    construct.Padding(3),
                    'more' / construct.Default(construct.Flag, False),
                    'disconnect' / construct.Flag,
                    'acknowledge' / construct.Flag,
                    'expect_receive' / construct.Flag,
                    'sequence_number' / construct.Flag,
                ),
                'message' / construct.Bytes(length=lambda ctx: ctx.length - 6),
                construct.Const(b'\x03'),  # etx
            ),
        ),
    ),
    'checksum' / construct.Checksum(
        construct.Int16ul, lifescan.crc_ccitt, construct.this.data),
)

_COMMAND_SUCCESS = construct.Const(b'\x05\x06')

_VERSION_REQUEST = construct.Const(b'\x05\x0d\x02')

_VERSION_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'version' / construct.PascalString(construct.Byte, encoding='ascii'),
)

_SERIAL_NUMBER_REQUEST = construct.Const(
    b'\x05\x0B\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00')

_SERIAL_NUMBER_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'serial_number' / construct.GreedyString(encoding='ascii'),
)

_DATETIME_REQUEST = construct.Struct(
    construct.Const(b'\x05\x20'),  # 0x20 is the datetime
    'request_type' / construct.Enum(construct.Byte, write=0x01, read=0x02),
    'timestamp' / construct.Default(
        construct_extras.Timestamp(construct.Int32ul),
        datetime.datetime(1970, 1, 1, 0, 0)),
)

_DATETIME_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'timestamp' / construct_extras.Timestamp(construct.Int32ul),
)

_GLUCOSE_UNIT_REQUEST = construct.Const(
    b'\x05\x09\x02\x09\x00\x00\x00\x00')

_GLUCOSE_MAPPING = {
    common.Unit.MG_DL: 0x00,
    common.Unit.MMOL_L: 0x01,
}

_GLUCOSE_UNIT_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'unit' / construct.SymmetricMapping(
        construct.Byte, _GLUCOSE_MAPPING),
    construct.Padding(3),
)

_MEMORY_ERASE_REQUEST = construct.Const(b'\x05\x1A')

_READING_COUNT_RESPONSE = construct.Struct(
    construct.Const(b'\x05\x0f'),
    'count' / construct.Int16ul,
)

_READ_RECORD_REQUEST = construct.Struct(
    construct.Const(b'\x05\x1f'),
    'record_id' / construct.Int16ul,
)

_READING_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'timestamp' / construct_extras.Timestamp(construct.Int32ul),
    'value' / construct.Int32ul,
)

class Device(serial.SerialDevice):
    BAUDRATE = 9600
    DEFAULT_CABLE_ID = '067b:2303'  # Generic PL2303 cable.
    TIMEOUT = 0.5

    def __init__(self, device):
        super(Device, self).__init__(device)

        self.sent_counter_ = False
        self.expect_receive_ = False
        self.buffered_reader_ = construct.Rebuffered(_PACKET, tailcutoff=1024)

    def connect(self):
        try:
            self._send_packet(b'', disconnect=True)
            self._read_ack()
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def disconnect(self):
        self.connect()

    def _send_packet(self, message, acknowledge=False, disconnect=False):
        pkt = _PACKET.build(
            {'value': {
                'message': message,
                'sequence_number': self.sent_counter_,
                'expect_receive': self.expect_receive_,
                'acknowledge': acknowledge,
                'disconnect': disconnect,
            }})
        logging.debug('sending packet: %s', binascii.hexlify(pkt))

        self.serial_.write(pkt)
        self.serial_.flush()

    def _read_packet(self):
        raw_pkt = self.buffered_reader_.parse_stream(self.serial_)
        logging.debug('received packet: %r', raw_pkt)

        # discard the checksum and copy
        pkt = raw_pkt.value

        if not pkt.disconnect and pkt.sequence_number != self.expect_receive_:
            raise lifescan.MalformedCommand(
                'at position 2[0b] expected %02x, received %02x' % (
                    self.expect_receive_, pkt.sequence_count))

        return pkt

    def _send_ack(self):
        self._send_packet(b'', acknowledge=True, disconnect=False)

    def _read_ack(self):
        pkt = self._read_packet()
        assert pkt.acknowledge

    def _send_request(self, request_format, *args):
        try:
            request = request_format.build(*args)
            self._send_packet(request, acknowledge=False, disconnect=False)

            self.sent_counter_ = not self.sent_counter_
            self._read_ack()
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def _read_response(self, response_format):
        try:
            pkt = self._read_packet()
            assert not pkt.acknowledge

            self.expect_receive_ = not self.expect_receive_
            self._send_ack()

            return response_format.parse(pkt.message)
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def get_meter_info(self):
        return common.MeterInfo(
            'OneTouch Ultra Easy glucometer',
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self.get_version(),),
            native_unit=self.get_glucose_unit())

    def get_version(self):
        self._send_request(_VERSION_REQUEST, None)

        response = self._read_response(_VERSION_RESPONSE)

        return response.version

    def get_serial_number(self):
        self._send_request(_SERIAL_NUMBER_REQUEST, None)

        response = self._read_response(_SERIAL_NUMBER_RESPONSE)
        return response.serial_number

    def get_datetime(self):
        self._send_request(
            _DATETIME_REQUEST, {'request_type': 'read'})
        response = self._read_response(_DATETIME_RESPONSE)
        return response.timestamp

    def set_datetime(self, date=datetime.datetime.now()):
        self._send_request(_DATETIME_REQUEST, {
            'request_type': 'write',
            'timestamp': date,
        })

        response = self._read_response(_DATETIME_RESPONSE)
        return response.timestamp

    def zero_log(self):
        self._send_request(_MEMORY_ERASE_REQUEST, None)
        self._read_response(_COMMAND_SUCCESS)

    def get_glucose_unit(self):
        self._send_request(_GLUCOSE_UNIT_REQUEST, None)
        response = self._read_response(_GLUCOSE_UNIT_RESPONSE)

        return response.unit

    def _get_reading(self, record_id):
        self._send_request(
            _READ_RECORD_REQUEST, {'record_id': record_id})
        return self._read_response(_READING_RESPONSE)

    def get_readings(self):
        self._send_request(
            _READ_RECORD_REQUEST, {'record_id': _INVALID_RECORD})
        count_response = self._read_response(_READING_COUNT_RESPONSE)

        for record_id in range(count_response.count):
            self._send_request(
                _READ_RECORD_REQUEST, {'record_id': record_id})
            reading = self._read_response(_READING_RESPONSE)

            yield common.GlucoseReading(
                reading.timestamp,
                float(reading.value))
