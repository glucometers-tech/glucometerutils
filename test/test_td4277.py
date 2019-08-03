# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the TD-4277 driver."""

# pylint: disable=protected-access,missing-docstring

import datetime

from absl.testing import parameterized

from glucometerutils.drivers import td4277
from glucometerutils.support import lifescan
from glucometerutils import exceptions


class TestTD4277Nexus(parameterized.TestCase):

    @parameterized.parameters(
        (b'\x21\x24\x0e\x15', datetime.datetime(2018, 1, 1, 21, 14)),
        (b'\x21\x26\x0e\x15', datetime.datetime(2019, 1, 1, 21, 14)),
        (b'\x04\x27\x25\x0d', datetime.datetime(2019, 8, 4, 13, 37)),
    )
    def test_parse_datetime(self, message, date):
        self.assertEqual(td4277._parse_datetime(message),
                         date)

    def test_making_message(self):
        self.assertEqual(
            td4277._make_packet(0x22, 0),
            b'\x51\x22\x00\x00\x00\x00\xa3\x16')
