# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2026 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Tests for the FreeStyle Freedom Lite driver."""

# pylint: disable=protected-access,missing-docstring

import datetime

from absl.testing import parameterized

from glucometerutils import exceptions
from glucometerutils.drivers import fsfreedomlite


class TestFreeStyleFreedomLite(parameterized.TestCase):
    @parameterized.named_parameters(
        (
            "three_letter_month",
            "123  Oct  03 2024 04:51 00 0x00",
            datetime.datetime(2024, 10, 3, 4, 51),
            123,
        ),
        (
            "june_in_full",
            "095  June 14 2024 18:07 00 0x00",
            datetime.datetime(2024, 6, 14, 18, 7),
            95,
        ),
        (
            "july_in_full",
            "210  July 25 2024 09:32 00 0x00",
            datetime.datetime(2024, 7, 25, 9, 32),
            210,
        ),
        (
            "glucose_type_letter",
            "150  Mar  01 2024 12:00 G 0x00",
            datetime.datetime(2024, 3, 1, 12, 0),
            150,
        ),
    )
    def test_parse_reading(self, line, timestamp, value):
        reading = fsfreedomlite._parse_reading(line)
        self.assertIsNotNone(reading)
        self.assertEqual(reading.timestamp, timestamp)
        self.assertEqual(reading.value, value)
        self.assertEqual(reading.comment, "")

    def test_parse_reading_nonzero_flags(self):
        reading = fsfreedomlite._parse_reading("101  Jan  09 2024 07:15 00 0x08")
        self.assertIsNotNone(reading)
        self.assertEqual(reading.timestamp, datetime.datetime(2024, 1, 9, 7, 15))
        self.assertEqual(reading.value, 101)
        self.assertEqual(reading.comment, "Flags: 0x08")

    def test_parse_reading_hi(self):
        reading = fsfreedomlite._parse_reading("HI   Feb  20 2024 22:40 00 0x00")
        self.assertIsNotNone(reading)
        self.assertEqual(reading.timestamp, datetime.datetime(2024, 2, 20, 22, 40))
        self.assertEqual(reading.value, float("inf"))

    def test_parse_reading_ketone_ignored(self):
        self.assertIsNone(
            fsfreedomlite._parse_reading("012  Apr  02 2024 08:00 K 0x00")
        )

    @parameterized.parameters(
        ("123  Oct  03 2024 04:51",),
        ("12a  Oct  03 2024 04:51 00 0x00",),
        ("123  Xyz  03 2024 04:51 00 0x00",),
        ("123  Oct  03 2024 04:51 00 0x0G",),
        ("Foo",),
    )
    def test_parse_reading_invalid(self, line):
        with self.assertRaises(exceptions.InvalidResponse):
            fsfreedomlite._parse_reading(line)
