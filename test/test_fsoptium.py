# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the FreeStyle Optium driver."""

# pylint: disable=protected-access,missing-docstring

import datetime

from absl.testing import parameterized

from glucometerutils.drivers import fsoptium
from glucometerutils import exceptions


class TestFreeStyleOptium(parameterized.TestCase):

    @parameterized.parameters(
        ('Clock:\tApr  22 2014\t02:14:37',
         datetime.datetime(2014, 4, 22, 2, 14, 37)),
        ('Clock:\tJul  10 2013\t14:26:44',
         datetime.datetime(2013, 7, 10, 14, 26, 44)),
        ('Clock:\tSep  29 2013\t17:35:34',
         datetime.datetime(2013, 9, 29, 17, 35, 34)),
    )
    def test_parse_clock(self, datestr, datevalue):
        self.assertEqual(
            fsoptium._parse_clock(datestr),
            datevalue)

    @parameterized.parameters(
        ('Apr 22 2014 02:14:37',),
        ('Clock:\tXxx  10 2013\t14:26',),
        ('Clock:\tSep  29 2013\t17:35:22.34',),
        ('Foo',)
    )
    def test_parse_clock_invalid(self, datestr):
        with self.assertRaises(exceptions.InvalidResponse):
            fsoptium._parse_clock(datestr)
