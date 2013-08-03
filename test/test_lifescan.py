# -*- coding: utf-8 -*-
"""Tests for the LifeScan Common functions."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

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
    self.assertEqual(0x0054, checksum)

    checksum = lifescan_common.calculate_checksum(
      bytes('T "SAT","08/03/13","22:12:00   "', 'ascii'))
    self.assertEqual(0x0608, checksum)

if __name__ == '__main__':
    unittest.main()
