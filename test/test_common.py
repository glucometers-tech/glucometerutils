# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the common routines."""

# pylint: disable=protected-access,missing-docstring

import datetime

from absl.testing import parameterized

from glucometerutils import common


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


class TestGlucoseReading(parameterized.TestCase):

    TEST_DATETIME = datetime.datetime(2018, 1, 1, 0, 30, 45)

    def test_minimal(self):
        reading = common.GlucoseReading(self.TEST_DATETIME, 100)
        self.assertEqual(reading.as_csv(common.Unit.MG_DL),
                         '"2018-01-01 00:30:45","100.00","","blood sample",""')

    @parameterized.named_parameters(
        ('_mgdl', common.Unit.MG_DL, 100),
        ('_mmoll', common.Unit.MMOL_L, 5.56))
    def test_value(self, unit, expected_value):
        reading = common.GlucoseReading(self.TEST_DATETIME, 100)
        self.assertAlmostEqual(
            reading.get_value_as(unit), expected_value, places=2)

    @parameterized.named_parameters(
        ('_meal_none',
         {'meal': common.Meal.NONE},
         '"2018-01-01 00:30:45","100.00","","blood sample",""'),
        ('_meal_before',
         {'meal': common.Meal.BEFORE},
         '"2018-01-01 00:30:45","100.00","Before Meal","blood sample",""'),
        ('_meal_after',
         {'meal': common.Meal.AFTER},
         '"2018-01-01 00:30:45","100.00","After Meal","blood sample",""'),
        ('_measurement_blood',
         {'measure_method': common.MeasurementMethod.BLOOD_SAMPLE},
         '"2018-01-01 00:30:45","100.00","","blood sample",""'),
        ('_measurement_cgm',
         {'measure_method': common.MeasurementMethod.CGM},
         '"2018-01-01 00:30:45","100.00","","CGM",""'),
        ('_comment',
         {'comment': 'too much'},
         '"2018-01-01 00:30:45","100.00","","blood sample","too much"'),
        ('_comment_quoted',
         {'comment': '"too" much'},
         '"2018-01-01 00:30:45","100.00","","blood sample","\"too\" much"'),
    )
    def test_csv(self, kwargs_dict, expected_csv):
        reading = common.GlucoseReading(
            self.TEST_DATETIME, 100, **kwargs_dict)
        self.assertEqual(reading.as_csv(common.Unit.MG_DL), expected_csv)


class TestMeterInfo(parameterized.TestCase):

    @parameterized.named_parameters(
        ('_no_serial_number',
         {},
         'Serial Number: N/A\n'),
        ('_serial_number',
         {'serial_number': 1234},
         'Serial Number: 1234\n'),
        ('_no_version_information',
         {},
         'Version Information:\n    N/A\n'),
        ('_version_information_1',
         {'version_info': ['test']},
         'Version Information:\n    test\n'),
        ('_version_information_2',
         {'version_info': ['test', 'test2']},
         'Version Information:\n    test\n    test2\n'),
        ('_default_native_unit',
         {},
         'Native Unit: mg/dL\n'),
    )
    def test_meter_info(self, kwargs_dict, expected_fragment):
        info = common.MeterInfo(self.id(), **kwargs_dict)
        self.assertIn(expected_fragment, str(info))
