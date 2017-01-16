# -*- coding: utf-8 -*-
"""Tests for the LifeScan OneTouch Ultra 2 driver."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import os
import sys
import unittest

import mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils.drivers import otultra2
from glucometerutils.support import lifescan
from glucometerutils import exceptions

class TestOTUltra2(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

        mock_serial = mock.patch('serial.Serial').start()
        self.mock_readline = mock_serial.return_value.readline

        self.device = otultra2.Device('mockdevice')

    def _set_return_string(self, string):
        self.mock_readline.return_value = bytes(string, 'ascii')

    def test_checksum(self):
        checksum = otultra2._calculate_checksum(bytes('T', 'ascii'))
        self.assertEqual(0x0054, checksum)

        checksum = otultra2._calculate_checksum(
            bytes('T "SAT","08/03/13","22:12:00   "', 'ascii'))
        self.assertEqual(0x0608, checksum)

    def test_missing_checksum(self):
        self._set_return_string('INVALID')

        self.assertRaises(lifescan.MissingChecksum,
                          self.device.get_serial_number)

    def test_short_response(self):
        self._set_return_string('.\r')

        self.assertRaises(exceptions.InvalidResponse,
                          self.device.get_serial_number)

    def test_invalid_response(self):
        self._set_return_string('% 2500\r')

        self.assertRaises(exceptions.InvalidResponse,
                          self.device.get_serial_number)

    def test_invalid_serial_number(self):
        self._set_return_string('@ "12345678O" 0297\r')

        self.assertRaises(lifescan.InvalidSerialNumber,
                          self.device.get_serial_number)

    def test_invalid_checksum(self):
        self._set_return_string('% 1337\r')

        self.assertRaises(exceptions.InvalidChecksum,
                          self.device.get_serial_number)

    def test_broken_checksum(self):
        self._set_return_string('% 13AZ\r')

        self.assertRaises(lifescan.MissingChecksum,
                          self.device.get_serial_number)

if __name__ == '__main__':
    unittest.main()
