# -*- coding: utf-8 -*-
"""Tests for the common routines."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import os
import sys
import unittest

from absl.testing import parameterized

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils import common
from glucometerutils import exceptions


class TestGlucoseConversion(parameterized.TestCase):

    def test_convert_to_mmol(self):
        self.assertEqual(
            5.56, common.convert_glucose_unit(
                100, common.Unit.MG_DL, common.Unit.MMOL_L))

    def test_convert_to_mgdl(self):
        self.assertEqual(
            180, common.convert_glucose_unit(
                10, common.Unit.MMOL_L, common.Unit.MG_DL))

    @parameterized.parameters(list(common.Unit))
    def test_convert_identity(self, unit):
        self.assertEqual(
            100, common.convert_glucose_unit(
                100, unit, unit))

    @parameterized.parameters([unit.value for unit in common.Unit])
    def test_convert_identity_str(self, unit_str):
        self.assertEqual(
            100, common.convert_glucose_unit(
                100, unit_str, unit_str))

    @parameterized.parameters(
        (common.Unit.MMOL_L, 'foo'),
        ('foo', common.Unit.MG_DL),
        (None, common.Unit.MG_DL),
        (common.Meal.NONE, common.Unit.MG_DL))
    def test_invalid_values(self, from_unit, to_unit):
        with self.assertRaises(Exception):
            common.convert_glucose_unit(100, from_unit, to_unit)


if __name__ == '__main__':
        unittest.main()
