# -*- coding: utf-8 -*-
"""Common utility functions for LifeScan meters."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

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
