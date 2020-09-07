# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2018 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Tests for the common routines."""

# pylint: disable=protected-access,missing-docstring

import datetime

import construct
from absl.testing import absltest

from glucometerutils.support import construct_extras

_TEST_DATE1 = datetime.datetime(1970, 1, 2, 0, 0)
_TEST_DATE2 = datetime.datetime(1971, 1, 1, 0, 0)
_TEST_DATE3 = datetime.datetime(1970, 1, 1, 0, 0)

_NEW_EPOCH = 31536000  # datetime.datetime(1971, 1, 1, 0, 0)


class TestTimestamp(absltest.TestCase):
    def test_build_unix_epoch(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.Int32ul).build(_TEST_DATE1),
            b"\x80\x51\x01\x00",
        )

    def test_parse_unix_epoch(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.Int32ul).parse(b"\x803\xe1\x01"),
            _TEST_DATE2,
        )

    def test_build_custom_epoch(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.Int32ul, epoch=_NEW_EPOCH).build(
                _TEST_DATE2
            ),
            b"\x00\x00\x00\x00",
        )

    def test_parse_custom_epoch(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.Int32ul, epoch=_NEW_EPOCH).parse(
                b"\x00\x00\x00\x00"
            ),
            _TEST_DATE2,
        )

    def test_build_custom_epoch_negative_failure(self):
        with self.assertRaises(construct.core.FormatFieldError):
            construct_extras.Timestamp(construct.Int32ul, epoch=_NEW_EPOCH).build(
                _TEST_DATE1
            )

    def test_build_custom_epoch_negative_success(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.Int32sl, epoch=_NEW_EPOCH).build(
                _TEST_DATE1
            ),
            b"\x00\x1e\x20\xfe",
        )

    def test_build_varint(self):
        self.assertEqual(
            construct_extras.Timestamp(construct.VarInt).build(_TEST_DATE3), b"\x00"
        )

    def test_invalid_value(self):
        with self.assertRaises(AssertionError):
            construct_extras.Timestamp(construct.Int32ul).build("foo")
