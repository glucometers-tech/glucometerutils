# -*- coding: utf-8 -*-
"""Common utility functions for LifeScan meters."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013-2017, Diego Elio Pettenò'
__license__ = 'MIT'

from glucometerutils import exceptions


class MissingChecksum(exceptions.InvalidResponse):
  """The response misses the expected 4-digits checksum."""
  def __init__(self, response):
    self.message = 'Response is missing checksum: %s' % response


class InvalidSerialNumber(exceptions.Error):
  """The serial number is not as expected."""
  def __init__(self, serial_number):
    self.message = 'Serial number %s is invalid.' % serial_number


class MalformedCommand(exceptions.InvalidResponse):
  def __init__(self, message):
    exceptions.InvalidResponse.__init__(
      self, 'Malformed command: %s' % message)


def crc_ccitt(data):
  """Calculate the CRC-16-CCITT with LifeScan's common seed.

  Args:
    data: (bytes) the data to calculate the checksum of

  Returns:
    (int) The 16-bit integer value of the CRC-CCITT calculated.

  This function uses the non-default 0xFFFF seed as used by multiple
  LifeScan meters.
  """
  crc = 0xffff

  for byte in data:
    crc = (crc >> 8) & 0xffff | (crc << 8) & 0xffff
    crc ^= byte
    crc ^= (crc & 0xff) >> 4
    crc ^= (((crc << 8) & 0xffff) << 4) & 0xffff
    crc ^= (crc & 0xff) << 5

  return (crc & 0xffff)
