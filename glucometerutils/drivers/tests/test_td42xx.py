# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2019 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Tests for the TD-42xx driver."""

# pylint: disable=protected-access,missing-docstring

import datetime

from absl.testing import parameterized

from glucometerutils.drivers import td42xx


class TestTD4277Nexus(parameterized.TestCase):
    @parameterized.parameters(
        (b"\x21\x24\x0e\x15", datetime.datetime(2018, 1, 1, 21, 14)),
        (b"\x21\x26\x0e\x15", datetime.datetime(2019, 1, 1, 21, 14)),
        (b"\x04\x27\x25\x0d", datetime.datetime(2019, 8, 4, 13, 37)),
    )
    def test_parse_datetime(self, message, date):
        self.assertEqual(td42xx._parse_datetime(message), date)

    def test_making_message(self):
        self.assertEqual(
            td42xx._make_packet(0x22, 0), b"\x51\x22\x00\x00\x00\x00\xa3\x16"
        )
