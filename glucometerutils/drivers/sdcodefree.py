# -*- coding: utf-8 -*-
"""Driver for SD CodeFree devices by SD Biosensor.

For SD Biosensor glucometers using the serial interface.

Supported features:
    - get readings, including pre-/post-meal notes;
    - set date and time.

Expected device path: /dev/ttyUSB0 or similar serial port device.

IMPORTANT NOTE: the glucometer can be connected before starting the program, but
it has to be turned on when the program asks you to.
"""


__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2017, Diego Elio Pettenò'
__license__ = 'MIT'

import array
import collections
import datetime
import functools
import logging
import operator
import struct
import time

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import serial

_STX = 0x53    # Not really 'STX'
_ETX = 0xAA    # Not really 'ETX'

_DIR_IN = 0x20
_DIR_OUT = 0x10

_IDX_STX = 0
_IDX_DIRECTION = 1
_IDX_LENGTH = 2
_IDX_CHECKSUM = -2
_IDX_ETX = -1

_RECV_PREAMBLE = b'\x53\x20'

_CHALLENGE_PACKET_FULL = b'\x53\x20\x04\x10\x30\x20\xAA'
_RESPONSE_PACKET = b'\x10\x40'

_DATE_SET_PACKET = b'\x10\x10'

_DISCONNECT_PACKET = b'\x10\x60'
_DISCONNECTED_PACKET = b'\x10\x70'

_STRUCT_READINGS_COUNT = struct.Struct('>H')

_FETCH_PACKET = b'\x10\x60'

_ReadingRecord = collections.namedtuple(
    '_ReadingRecord',
    ('unknown1', 'unknown2', 'year', 'month', 'day', 'hour', 'minute',
     'value', 'meal_flag'))
_STRUCT_READING = struct.Struct('>BBBBBBBHB')

_MEAL_FLAG = {
    0x00: common.NO_MEAL,
    0x10: common.BEFORE_MEAL,
    0x20: common.AFTER_MEAL
}

def parse_reading(msgdata):
    return _ReadingRecord(*_STRUCT_READING.unpack_from(msgdata))

def xor_checksum(msg):
    return functools.reduce(operator.xor, msg)

class Device(serial.SerialDevice):
    BAUDRATE = 38400
    DEFAULT_CABLE_ID = '10c4:ea60'  # Generic cable.
    TIMEOUT = 300  # We need to wait for data from the device.

    def read_packet(self):
        preamble = self.serial_.read(3)
        if len(preamble) != 3:
            raise exceptione.InvalidResponse(
                response='Expected 3 bytes, received %d' % len(preamble))
        if preamble[0:_IDX_LENGTH] != _RECV_PREAMBLE:
            raise exceptions.InvalidResponse(
                response='Unexpected preamble %r' % pramble[0:_IDX_LENGTH])

        msglen = preamble[_IDX_LENGTH]
        message = self.serial_.read(msglen)
        if len(message) != msglen:
            raise exception.InvalidResponse(
                response='Expected %d bytes, received %d' %
                (msglen, len(message)))
        if message[_IDX_ETX] != _ETX:
            raise exception.InvalidResponse(
                response='Unexpected end-of-transmission byte: %02x' %
                message[_IDX_ETX])

        # Calculate the checksum up until before the checksum itself.
        msgdata = message[:_IDX_CHECKSUM]

        cksum = xor_checksum(msgdata)
        if cksum != message[_IDX_CHECKSUM]:
            raise exception.InvalidChecksum(message[_IDX_CHECKSUM], cksum)

        return msgdata

    def wait_and_ready(self):
        challenge = self.serial_.read(1)

        # The first packet read may have a prefixed zero, it might be a bug in
        # the cp210x driver or device, but discard it if found.
        if challenge == b'\0':
            challege = self.serial_.read(1)
            if challenge != b'\x53':
                raise exceptions.ConnectionFailed(
                    message='Unexpected starting bytes %r' % challenge)

        challenge += self.serial_.read(6)

        if challenge != _CHALLENGE_PACKET_FULL:
            raise exceptions.ConnectionFailed(
                message='Unexpected challenge %r' % challenge)

        self.send_packet(_RESPONSE_PACKET)

        # The first packet only contains the counter of how many readings are
        # available.
        first_packet = self.read_packet()

        count = _STRUCT_READINGS_COUNT.unpack_from(first_packet, 1)

        return count[0]

    def send_packet(self, msgdata):
        packet = array.array('B')
        packet.extend((_STX, _DIR_OUT, len(msgdata)+2))
        packet.extend(msgdata)
        packet.extend((xor_checksum(msgdata), _ETX))
        self.serial_.write(packet.tobytes())

    def connect(self):
        print("Please connect and turn on the device.")

    def disconnect(self):
        self.send_packet(_DISCONNECT_PACKET)
        response = self.read_packet()
        if response != _DISCONNECTED_PACKET:
            raise exceptions.InvalidResponse(response=response)

    def get_meter_info(self):
        return common.MeterInfo('SD CodeFree glucometer')

    def get_version(self):
        raise NotImplementedError

    def get_serial_number(self):
        raise NotImplementedError

    def get_glucose_unit(self):
        # Device does not provide information on glucose unit.
        return common.UNIT_MGDL

    def get_datetime(self):
        raise NotImplementedError

    def set_datetime(self, date=datetime.datetime.now()):
        setdatecmd = date.strftime('ADATE%Y%m%d%H%M').encode('ascii')

        # Ignore the readings count.
        self.wait_and_ready()

        self.send_packet(setdatecmd)
        response = self.read_packet()
        if response != _DATE_SET_PACKET:
            raise exceptions.InvalidResponse(response=response)

        # The date we return should only include up to minute, unfortunately.
        return datetime.datetime(date.year, date.month, date.day,
                                 date.hour, date.minute)

    def zero_log(self):
        raise NotmplementedError

    def get_readings(self):
        count = self.wait_and_ready()

        for _ in range(count):
            self.send_packet(_FETCH_PACKET)
            rpkt = self.read_packet()

            r = parse_reading(rpkt)
            meal = _MEAL_FLAG[r.meal_flag]

            yield common.GlucoseReading(
                datetime.datetime(
                    2000 + r.year, r.month, r.day, r.hour, r.minute),
                r.value, meal=meal)
