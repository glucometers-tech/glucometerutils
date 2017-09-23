# -*- coding: utf-8 -*-
"""Driver for LifeScan OneTouch Verio (2015) and Select Plus devices.

Verio 2015 devices can be recognized by microUSB connectors.

Supported features:
    - get readings, including pre-/post-meal notes †;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/sdb or similar USB block device.

† Pre-/post-meal notes are only supported on Select Plus devices.

Further information on the device protocol can be found at

https://flameeyes.github.io/glucometer-protocols/lifescan/onetouch-verio-2015

"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2016-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import binascii
import datetime
import logging
import struct

from pyscsi.pyscsi.scsi import SCSI
from pyscsi.pyscsi.scsi_device import SCSIDevice

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import lifescan

# Match the same values in the otultraeasy driver.
_STX = 0x02
_ETX = 0x03

# This device uses SCSI blocks as registers.
_REGISTER_SIZE = 512

_STRUCT_PREAMBLE = struct.Struct('<BH')
_STRUCT_CODA = _STRUCT_PREAMBLE  # they are actually the same, mirrored.

_STRUCT_UINT16 = struct.Struct('<H')
_STRUCT_UINT32 = struct.Struct('<I')

_STRUCT_CHECKSUM = _STRUCT_UINT16
_STRUCT_TIMESTAMP = _STRUCT_UINT32
_STRUCT_RECORDID = _STRUCT_UINT16
_STRUCT_READING = _STRUCT_UINT32
_STRUCT_RECORD = struct.Struct('<BBHBHIHBBBBB')

_QUERY_REQUEST = b'\x04\xe6\x02'
_QUERY_KEY_SERIAL = b'\x00'
_QUERY_KEY_MODEL = b'\x01'
_QUERY_KEY_SOFTWARE = b'\x02'

_READ_PARAMETER_REQUEST = b'\x04'
_PARAMETER_KEY_UNIT = b'\x04'

_READ_RTC_REQUEST = b'\x04\x20\x02'
_WRITE_RTC_REQUEST = b'\x04\x20\x01'
# All timestamp reported by this device are seconds since this date.
_EPOCH_BASE = 946684800  # 2010-01-01 00:00

_READ_RECORD_COUNT_REQUEST = b'\x04\x27\x00'
_READ_RECORD_REQUEST_PREFIX = b'\x04\x31\x02'
_READ_RECORD_REQUEST_SUFFIX = b'\x00'

_MEMORY_ERASE_REQUEST = b'\x04\x1a'

_MEAL_CODES = {
  0x00: common.NO_MEAL,
  0x01: common.BEFORE_MEAL,
  0x02: common.AFTER_MEAL,
}

def _extract_message(register):
  """Parse the message preamble and verify checksums."""
  stx, length = _STRUCT_PREAMBLE.unpack_from(register)
  if stx != _STX:
    raise lifescan.MalformedCommand(
      'invalid STX byte: %02x' % stx)
  if length > _REGISTER_SIZE:
    raise lifescan.MalformedCommand(
      'invalid length: %d > REGISTER_SIZE' % length)

  # 2 is the length of the checksum, so it should be ignored.
  calculated_checksum = lifescan.crc_ccitt(register[:(length-2)])

  coda_offset = length - _STRUCT_CODA.size
  etx, encoded_checksum = _STRUCT_CODA.unpack_from(register[coda_offset:])
  if etx != _ETX:
    raise lifescan.MalformedCommand(
      'invalid ETX byte: %02x' % etx)
  if encoded_checksum != calculated_checksum:
    raise exceptions.InvalidChecksum(encoded_checksum, calculated_checksum)

  response = register[_STRUCT_PREAMBLE.size:coda_offset]

  logging.debug('Read packet: %s' % binascii.hexlify(response))
  return response

def _encode_message(cmd):
  """Add message preamble and calculate checksum, add padding."""
  length = len(cmd) + _STRUCT_PREAMBLE.size + _STRUCT_CODA.size
  preamble = _STRUCT_PREAMBLE.pack(_STX, length)
  message = preamble + cmd + bytes((_ETX,))
  checksum = _STRUCT_CHECKSUM.pack(lifescan.crc_ccitt(message))
  message += checksum

  logging.debug('Sending packet: %s' % binascii.hexlify(message))

  # Pad the message to match the size of the register.
  return message + bytes(_REGISTER_SIZE - len(message))

def _convert_timestamp(timestamp):
  return datetime.datetime.utcfromtimestamp(timestamp + _EPOCH_BASE)

class Device(object):
  def __init__(self, device):
    if not device:
      raise exceptions.CommandLineError(
        '--device parameter is required, should point to the disk device '
        'representing the meter.')

    self.device_name_ = device
    self.scsi_device_ = SCSIDevice(device, readwrite=True)
    self.scsi_ = SCSI(self.scsi_device_)
    self.scsi_.blocksize = _REGISTER_SIZE

  def _send_message(self, cmd, lba):
    """Send a request to the meter, and read its response.

    Args:
      cmd: (bytes) the raw command to send the device, without
        preamble or checksum.
      lba: (int) the address of the block register to use, known
        valid addresses are 3, 4 and 5.

    Returns:
      (bytes) The raw response from the meter. No preamble or coda is
      present, and the checksum has already been validated.
    """
    self.scsi_.write10(lba, 1, _encode_message(cmd))
    response = self.scsi_.read10(lba, 1)
    # TODO: validate that the response is valid.
    return _extract_message(response.datain)

  def connect(self):
    inq = self.scsi_.inquiry()
    vendor = inq.result['t10_vendor_identification'][:32]
    if vendor != b'LifeScan':
      raise exceptions.ConnectionFailed(
        'Device %s is not a LifeScan glucometer.' % self.device_name_)

  def disconnect(self):
    return

  def get_meter_info(self):
    return common.MeterInfo(
      'OneTouch %s glucometer' % self._query_string(_QUERY_KEY_MODEL),
      serial_number=self.get_serial_number(),
      version_info=(
        'Software version: ' + self.get_version(),),
      native_unit=self.get_glucose_unit())

  def _query_string(self, query_key):
    response = self._send_message(_QUERY_REQUEST + query_key, 3)
    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))
    # Strings are encoded in wide characters (LE), but they should
    # only contain ASCII characters. Note that the string is
    # null-terminated, so the last character should be dropped.
    return response[2:].decode('utf-16-le')[:-1]

  def _read_parameter(self, parameter_key):
    response = self._send_message(
      _READ_PARAMETER_REQUEST + parameter_key, 4)
    if response[0:2] != b'\x03\x06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 03 06, received %02x %02x' % (
          response[0], response[1]))
    return response[2:]

  def get_serial_number(self):
    return self._query_string(_QUERY_KEY_SERIAL)

  def get_version(self):
    return self._query_string(_QUERY_KEY_SOFTWARE)

  def get_datetime(self):
    response = self._send_message(_READ_RTC_REQUEST, 3)
    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))
    (timestamp,) = _STRUCT_TIMESTAMP.unpack(response[2:])
    return _convert_timestamp(timestamp)

  def set_datetime(self, date=datetime.datetime.now()):
    epoch = datetime.datetime.utcfromtimestamp(_EPOCH_BASE)
    delta = date - epoch
    timestamp = int(delta.total_seconds())

    timestamp_bytes = _STRUCT_TIMESTAMP.pack(timestamp)
    response = self._send_message(_WRITE_RTC_REQUEST + timestamp_bytes, 3)

    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))

    # The device does not return the new datetime, so confirm by
    # calling READ RTC again.
    return self.get_datetime()

  def zero_log(self):
    response = self._send_message(_MEMORY_ERASE_REQUEST, 3)
    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))

  def _get_reading_count(self):
    response = self._send_message(_READ_RECORD_COUNT_REQUEST, 3)
    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))

    (record_count,) = _STRUCT_RECORDID.unpack(response[2:])
    return record_count

  def get_glucose_unit(self):
    unit_value = self._read_parameter(_PARAMETER_KEY_UNIT)
    if unit_value == b'\x00\x00\x00\x00':
      return common.UNIT_MGDL
    elif unit_value == b'\x01\x00\x00\x00':
      return common.UNIT_MMOLL
    else:
      raise exceptions.InvalidGlucoseUnit('%r' % unit_value)

  def _get_reading(self, record_number):
    request = (_READ_RECORD_REQUEST_PREFIX +
               _STRUCT_RECORDID.pack(record_number) +
               _READ_RECORD_REQUEST_SUFFIX)
    response = self._send_message(request, 3)
    if response[0:2] != b'\x04\06':
      raise lifescan.MalformedCommand(
        'invalid response, expected 04 06, received %02x %02x' % (
          response[0], response[1]))

    (unused_const1, unused_const2, unused_counter, unused_const3,
     unused_counter2, timestamp, value, meal_flag, unused_const4, unused_flags,
     unused_const5, unused_const6) = _STRUCT_RECORD.unpack(
       response)

    return common.GlucoseReading(
      _convert_timestamp(timestamp), float(value), meal=_MEAL_CODES[meal_flag])

  def get_readings(self):
    record_count = self._get_reading_count()
    for record_number in range(record_count):
      yield self._get_reading(record_number)
