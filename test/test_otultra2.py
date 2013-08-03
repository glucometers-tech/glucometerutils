"""Tests for the LifeScan OneTouch Ultra 2 driver."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

import os
import sys
import unittest

import mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils import common
from glucometerutils.drivers import otultra2
from glucometerutils import exceptions

class TestOTUltra2(unittest.TestCase):
  def setUp(self):
    self.addCleanup(mock.patch.stopall)

    mock_serial = mock.patch('serial.Serial').start()
    self.mock_readline = mock_serial.return_value.readline

    self.device = otultra2.Device('mockdevice')

  def testMissingChecksum(self):
    self.mock_readline.return_value = bytes('INVALID', 'ascii')

    self.assertRaises(otultra2.MissingChecksum,
                      self.device.GetSerialNumber)

  def testShortResponse(self):
    self.mock_readline.return_value = bytes('.\r', 'ascii')

    self.assertRaises(exceptions.InvalidResponse,
                      self.device.GetSerialNumber)

  def testInvalidResponse(self):
    self.mock_readline.return_value = bytes('% 1337\r', 'ascii')

    self.assertRaises(exceptions.InvalidResponse,
                      self.device.GetSerialNumber)

  def testInvalidSerialNumber(self):
    self.mock_readline.return_value = bytes(
      '@ "12345678O" 1337\r', 'ascii')

    self.assertRaises(otultra2.InvalidSerialNumber,
                      self.device.GetSerialNumber)

if __name__ == '__main__':
    unittest.main()
