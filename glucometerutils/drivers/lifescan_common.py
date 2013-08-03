# -*- coding: utf-8 -*-
"""Common utility functions for LifeScan meters."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

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
  """Calculate the checksum used by OneTouch Ultra and Ultra2 devices

  Args:
    bytestring: the string of which the checksum has to be calculated.

  Returns:
    A string with the hexdecimal representation of the checksum for the input.

  The checksum is a very stupid one: it just sums all the bytes,
  modulo 16-bit, without any parity.
  """
  checksum = 0

  for byte in bytestring:
    checksum = (checksum + byte) & 0xffff

  return checksum
