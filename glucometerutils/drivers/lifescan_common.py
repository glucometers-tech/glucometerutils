# -*- coding: utf-8 -*-
"""Common utility functions for LifeScan meters."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

import ctypes

from glucometerutils import exceptions


class MissingChecksum(exceptions.InvalidResponse):
  """The response misses the expected 4-digits checksum."""
  def __init__(self, response):
    self.message = 'Response is missing checksum: %s' % response


class InvalidChecksum(exceptions.InvalidResponse):
  def __init__(self, expected, gotten):
    self.message = (
      'Response checksum not matching: %04x expected, %04x gotten' %
      (expected, gotten))


class InvalidSerialNumber(exceptions.Error):
  """The serial number is not as expected."""
  def __init__(self, serial_number):
    self.message = 'Serial number %s is invalid.' % serial_number


def calculate_checksum(bytestring):
  """Calculate the "CRC16 Sick" style checksum for LifeScan protocols.

  Args:
    bytestring: the string of which the checksum has to be calculated.

  Returns:
    A 16-bit integer that is the checksum for the input.

  Credits for this code go to Christian Navalici, who implemented it in his
  library at https://github.com/cristianav/PyCRC/ .
  """
  crcValue = 0x0000
  prev_c = 0x0000

  for idx, c in enumerate(bytestring):
    short_c  =  0x00ff & c

    idx_previous = idx - 1
    short_p  = ( 0x00ff & prev_c) << 8;

    if ( crcValue & 0x8000 ):
      crcValue = ctypes.c_ushort(crcValue << 1).value ^ 0x8005
    else:
      crcValue = ctypes.c_ushort(crcValue << 1).value

    crcValue &= 0xffff
    crcValue ^= ( short_c | short_p )

    prev_c = short_c

  # After processing, the one's complement of the CRC is calcluated and the
  # two bytes of the CRC are swapped.
  low_byte   = (crcValue & 0xff00) >> 8
  high_byte  = (crcValue & 0x00ff) << 8
  crcValue   = low_byte | high_byte;

  return crcValue
