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

import array
import datetime
import logging
import re
import struct
import time

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import lifescan
from glucometerutils.support import serial

_STX = 0x02
_ETX = 0x03

_IDX_STX = 0
_IDX_LENGTH = 1
_IDX_CONTROL = 2
_IDX_DATA = 3
_IDX_ETX = -3
_IDX_CHECKSUM = -2

_BIT_SENT_COUNTER = 0x01
_BIT_EXPECT_RECEIVE = 0x02
_BIT_ACK = 0x04
_BIT_DISCONNECT = 0x08
_BIT_MORE = 0x10

_READ_SERIAL_NUMBER = b'\x05\x0B\x02\x00\x00\x00\x00\x84\x6A\xE8\x73\x00'
_READ_VERSION = b'\x05\x0D\x02'
_READ_GLUCOSE_UNIT = b'\x05\x09\x02\x09\x00\x00\x00\x00'
_DELETE_RECORDS = b'\x05\x1A'
_READ_DATETIME = b'\x05\x20\x02\x00\x00\x00\x00'
_WRITE_DATETIME = b'\x05\x20\x01'
_READ_RECORD = b'\x05\x1F'

_INVALID_RECORD = 501

_STRUCT_TIMESTAMP = struct.Struct('<I')
_STRUCT_RECORDID = struct.Struct('<H')


class UnsetPacketError(LookupError):
  pass


def _convert_timestamp(timestamp_bytes):
  timestamp, = _STRUCT_TIMESTAMP.unpack(timestamp_bytes)

  return datetime.datetime.fromtimestamp(timestamp)


class _Packet(object):
  _STRUCT = struct.Struct('<H')

  def __init__(self):
    self.cmd = array.array('B')

  def read_from(self, serial):
    self.cmd.extend(serial.read(3))

    if self.cmd[_IDX_STX] != _STX:
      raise lifescan_command.MalformedCommand(
        'at position %s expected %02x, received %02x' % (
          _IDX_STX, _STX, self.cmd[_IDX_STX]))

    # the length includes prelude and appendix, which are six bytes total.
    if self.length > 6:
      self.cmd.extend(serial.read(self.length - 6))

    self.cmd.extend(serial.read(3))

    if self.cmd[_IDX_ETX] != _ETX:
      raise lifescan_command.MalformedCommand(
        'at position %s expected %02x, received %02x' % (
          _IDX_ETX, _ETX, self.cmd[_IDX_ETX]))

  def build_command(self, cmd_bytes):
    self.cmd.append(_STX)
    self.cmd.append(6 + len(cmd_bytes))
    self.cmd.append(0x00)  # link control
    self.cmd.extend(cmd_bytes)
    self.cmd.extend([_ETX, 0x00, 0x00])

  @property
  def length(self):
    if not self.cmd:
      return None

    return self.cmd[_IDX_LENGTH]

  def __is_in_control(self, bitmask):
    if not self.cmd:
      return None

    return bool(self.cmd[_IDX_CONTROL] & bitmask)

  def __set_in_control(self, bitmask, value):
    if not self.cmd:
      return None

    if value:
      self.cmd[_IDX_CONTROL] |= bitmask
    else:
      self.cmd[_IDX_CONTROL] &= (~bitmask) & 0xFF

    return value

  @property
  def sent_counter(self):
    return self.__is_in_control(_BIT_SENT_COUNTER)

  @sent_counter.setter
  def sent_counter(self, value):
    self.__set_in_control(_BIT_SENT_COUNTER, value)

  @property
  def expect_receive(self):
    return self.__is_in_control(_BIT_EXPECT_RECEIVE)

  @expect_receive.setter
  def expect_receive(self, value):
    self.__set_in_control(_BIT_EXPECT_RECEIVE, value)

  @property
  def checksum(self):
    return lifescan.crc_ccitt(self.cmd[:_IDX_CHECKSUM].tobytes())

  @property
  def acknowledge(self):
    return self.__is_in_control(_BIT_ACK)

  @acknowledge.setter
  def acknowledge(self, value):
    self.__set_in_control(_BIT_ACK, value)

  @property
  def disconnect(self):
    return self.__is_in_control(_BIT_DISCONNECT)

  @disconnect.setter
  def disconnect(self, value):
    self.__set_in_control(_BIT_DISCONNECT, value)

  @property
  def more(self):
    return self.__is_in_control(_BIT_MORE)

  @more.setter
  def more(self, value):
    self.__set_in_control(_BIT_MORE, value)

  def validate_checksum(self):
    expected_checksum = self.checksum
    received_checksum = self._STRUCT.unpack(self.cmd[_IDX_CHECKSUM:])[0]
    if received_checksum != expected_checksum:
      raise exceptions.InvalidChecksum(expected_checksum, received_checksum)

  def update_checksum(self):
    self._STRUCT.pack_into(self.cmd, _IDX_CHECKSUM, self.checksum)

  def tobytes(self):
    return self.cmd.tobytes()

  @property
  def data(self):
    return self.cmd[_IDX_DATA:_IDX_ETX]


class Device(serial.SerialDevice):
  BAUDRATE = 9600
  DEFAULT_CABLE_ID = '067b:2303'  # Generic PL2303 cable.

  def __init__(self, device):
    super(Device, self).__init__(device)

    self.sent_counter_ = False
    self.expect_receive_ = False

  def connect(self):
    self._send_command('', disconnect=True)

  def disconnect(self):
    self.connect()

  def _read_response(self):
    response = _Packet()

    response.read_from(self.serial_)

    if not response.disconnect and response.sent_counter != self.expect_receive_:
      raise lifescan_command.MalformedCommand(
        'at position 2[0b] expected %02x, received %02x' % (
          self.expect_receive_, response.expect_receive))

    if not response.acknowledge:
      self.expect_receive_ = not self.expect_receive_

    response.validate_checksum()

    if not response.acknowledge:
      self._send_command('', acknowledge=True)

    return response

  def _send_command(self, cmd_bytes, acknowledge=False, disconnect=False):
    cmd = _Packet()

    # set the proper expectations
    cmd.build_command(cmd_bytes)
    cmd.sent_counter = self.sent_counter_
    cmd.expect_receive = self.expect_receive_
    cmd.acknowledge = acknowledge
    cmd.disconnect = disconnect

    cmd.update_checksum()

    self.serial_.write(cmd.tobytes())
    self.serial_.flush()

    if not acknowledge:
      self.sent_counter_ = not self.sent_counter_
      result = self._read_response()
      return result

  def get_meter_info(self):
    return common.MeterInfo(
      'OneTouch Ultra Easy glucometer',
      serial_number=self.get_serial_number(),
      version_info=(
        'Software version: ' + self.get_version(),),
      native_unit=self.get_glucose_unit())

  def get_version(self):
    result = self._send_command(_READ_VERSION)

    response = self._read_response()

    return response.data[3:].tobytes().decode('ascii')

  def get_serial_number(self):
    result = self._send_command(_READ_SERIAL_NUMBER)

    response = self._read_response()

    return response.data[2:].tobytes().decode('ascii')

  def get_datetime(self):
    result = self._send_command(_READ_DATETIME)
    response = self._read_response()

    return _convert_timestamp(response.data[2:6])

  def set_datetime(self, date=datetime.datetime.now()):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = date - epoch
    timestamp = int(delta.total_seconds())

    timestamp_bytes = _STRUCT_TIMESTAMP.pack(timestamp)

    result = self._send_command(_WRITE_DATETIME + timestamp_bytes)

    response = self._read_response()
    return _convert_timestamp(response.data[2:6])

  def zero_log(self):
    result = self._send_command(_DELETE_RECORDS)
    response = self._read_response()

    if response.data.tobytes() != b'\x05\x06':
      raise exceptions.InvalidResponse(response.data)

  def get_glucose_unit(self):
    result = self._send_command(_READ_GLUCOSE_UNIT)
    response = self._read_response()

    if response.data[2] == 0:
      return common.UNIT_MGDL
    elif response.data[2] == 1:
      return common.UNIT_MMOLL
    else:
      raise lifescan_command.MalformedCommand(
        'at position PM1 invalid value %02x for unit' % response.data[2])

  def _get_reading(self, record_id):
    id_bytes = _STRUCT_RECORDID.pack(record_id)

    result = self._send_command(_READ_RECORD + id_bytes)
    return self._read_response()

  def get_readings(self):
    count_response = self._get_reading(_INVALID_RECORD)

    record_count, = _STRUCT_RECORDID.unpack_from(count_response.data, 2)

    for record_id in range(record_count):
      record_response = self._get_reading(record_id)

      timestamp = _convert_timestamp(record_response.data[2:6])
      value, = _STRUCT_TIMESTAMP.unpack_from(record_response.data, 6)

      yield common.GlucoseReading(timestamp, float(value))
