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
                100, common.Unit.MG_DL, common.Unit.MMOL_L))

        self.assertEqual(
            180, common.convert_glucose_unit(
                10, common.Unit.MMOL_L, common.Unit.MG_DL))

        self.assertEqual(
            100, common.convert_glucose_unit(
                100, common.Unit.MG_DL, common.Unit.MG_DL))

        self.assertEqual(
            10, common.convert_glucose_unit(
                10, common.Unit.MMOL_L, common.Unit.MMOL_L))

        self.assertRaises(
            ValueError,
            common.convert_glucose_unit, 10, common.Unit.MMOL_L, 'foo')

if __name__ == '__main__':
        unittest.main()
