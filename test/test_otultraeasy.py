# -*- coding: utf-8 -*-
"""Tests for the LifeScan OneTouch Ultra Mini driver."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import array
import os
import sys
import unittest
from unittest import mock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils.drivers import otultraeasy
from glucometerutils.support import lifescan
from glucometerutils import exceptions

class TestOTUltraMini(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)

        mock_serial = mock.patch('serial.Serial').start()
        self.mock_readline = mock_serial.return_value.readline

        self.device = otultraeasy.Device('mockdevice')

    def test_crc(self):
        self.assertEqual(
            0x41cd,
            lifescan.crc_ccitt(b'\x02\x06\x06\x03'))

    def test_crc_array(self):
        cmd_array = array.array('B', b'\x02\x06\x08\x03')
        self.assertEqual(
            0x62C2,
            lifescan.crc_ccitt(cmd_array))


if __name__ == '__main__':
    unittest.main()
