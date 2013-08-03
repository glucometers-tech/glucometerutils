"""Tests for the common routines."""

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
from glucometerutils import exceptions

class TestCommon(unittest.TestCase):
  def setUp(self):
    pass

  def testGlucoseConversion(self):
    self.assertEqual(
      5.56, common.ConvertGlucoseUnit(
        100, common.UNIT_MGDL, common.UNIT_MMOLL))

    self.assertEqual(
      5.56, common.ConvertGlucoseUnit(
        100, common.UNIT_MGDL))

    self.assertEqual(
      180, common.ConvertGlucoseUnit(
        10, common.UNIT_MMOLL, common.UNIT_MGDL))

    self.assertEqual(
      180, common.ConvertGlucoseUnit(
        10, common.UNIT_MMOLL))

    self.assertEqual(
      100, common.ConvertGlucoseUnit(
        100, common.UNIT_MGDL, common.UNIT_MGDL))

    self.assertEqual(
      10, common.ConvertGlucoseUnit(
        10, common.UNIT_MMOLL, common.UNIT_MMOLL))

    self.assertRaises(
      exceptions.InvalidGlucoseUnit,
      common.ConvertGlucoseUnit, common.UNIT_MMOLL, 'foo')

if __name__ == '__main__':
    unittest.main()
