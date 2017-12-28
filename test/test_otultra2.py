# -*- coding: utf-8 -*-
"""Tests for the LifeScan OneTouch Ultra 2 driver."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import os
import sys
import unittest
from unittest import mock

from absl.testing import parameterized

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils.drivers import otultra2
from glucometerutils.support import lifescan
from glucometerutils import exceptions

class TestOTUltra2(parameterized.TestCase):

    def test_checksum(self):
        checksum = otultra2._calculate_checksum(b'T')
        self.assertEqual(0x0054, checksum)

    def test_checksum_full(self):
        checksum = otultra2._calculate_checksum(
            b'T "SAT","08/03/13","22:12:00   "')
        self.assertEqual(0x0608, checksum)

    @parameterized.named_parameters(
        ('_missing_checksum', b'INVALID', lifescan.MissingChecksum),
        ('_short', b'.\r', exceptions.InvalidResponse),
        ('_generic', b'% 2500\r', exceptions.InvalidResponse),
        ('_invalid_serial_number', b'@ "12345678O" 0297\r',
         lifescan.InvalidSerialNumber),
        ('_invalid_checksum', b'% 1337\r', exceptions.InvalidChecksum),
        ('_broken_checksum', b'% 13AZ\r', lifescan.MissingChecksum),
    )
    def test_invalid_response(self, returned_string, expected_exception):
        with mock.patch('serial.Serial') as mock_serial:
            mock_serial.return_value.readline.return_value = returned_string

            device = otultra2.Device('mockdevice')
            with self.assertRaises(expected_exception):
                device.get_serial_number()

if __name__ == '__main__':
    unittest.main()
