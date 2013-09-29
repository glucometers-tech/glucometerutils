# -*- coding: utf-8 -*-
"""Tests for the common routines."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils import common
from glucometerutils import exceptions

class TestCommon(unittest.TestCase):
    def test_glucose_conversion(self):
        self.assertEqual(
            5.56, common.convert_glucose_unit(
                100, common.UNIT_MGDL, common.UNIT_MMOLL))

        self.assertEqual(
            5.56, common.convert_glucose_unit(
                100, common.UNIT_MGDL))

        self.assertEqual(
            180, common.convert_glucose_unit(
                10, common.UNIT_MMOLL, common.UNIT_MGDL))

        self.assertEqual(
            180, common.convert_glucose_unit(
                10, common.UNIT_MMOLL))

        self.assertEqual(
            100, common.convert_glucose_unit(
                100, common.UNIT_MGDL, common.UNIT_MGDL))

        self.assertEqual(
            10, common.convert_glucose_unit(
                10, common.UNIT_MMOLL, common.UNIT_MMOLL))

        self.assertRaises(
            exceptions.InvalidGlucoseUnit,
            common.convert_glucose_unit, common.UNIT_MMOLL, 'foo')

if __name__ == '__main__':
        unittest.main()
