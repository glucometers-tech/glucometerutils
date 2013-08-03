# -*- coding: utf-8 -*-
"""Tests for the LifeScan Common functions."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils import common
from glucometerutils.drivers import lifescan_common
from glucometerutils import exceptions


class TestOTUltra2(unittest.TestCase):
  def testChecksum(self):
    checksum = lifescan_common.calculate_checksum(bytes('T', 'ascii'))
    self.assertEqual(0x5400, checksum)

    checksum = lifescan_common.calculate_checksum(bytes('TestString', 'ascii'))
    self.assertEqual(0x0643, checksum)

if __name__ == '__main__':
    unittest.main()
