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

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils.support import lifescan

class TestChecksum(unittest.TestCase):
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
