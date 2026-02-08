# SPDX-FileCopyrightText: 2026 The glucometerutils Authors
#
# SPDX-License-Identifier: MIT

"""Tests for the Contour Next protocol support."""

# pylint: disable=protected-access,missing-docstring

import datetime
from unittest.mock import Mock

from absl.testing import absltest

from glucometerutils.support import contourusb


class TestContourNext(absltest.TestCase):
    header_record = b"\x04\x021H|\\^&||0t4cvJ|Contour7900^02.13\\01.00\\02.40^7901H33A1578|A=0^C=6^R=0^S=0^U=0^V=10600^X=070070180130^a=0^J=0|25|||||P|1|20260208104218|\r\x171A\r\n\x05"

    def setUp(self):
        super().setUp()
        self.mock_dev = Mock()
        self.mock_dev._header_record_re = contourusb._HEADER_RECORD_RE_NEXT

    def test_get_datetime(self):
        self.mock_dev.datetime = "20260208104218"
        self.assertEqual(
            datetime.datetime(2026, 2, 8, 10, 42, 18),
            contourusb.ContourHidDevice.get_datetime(self.mock_dev),
        )

    def test_RECORD_FORMAT_match(self):
        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find("\x02")

        result = contourusb._RECORD_FORMAT.match(header_record_decoded[stx:]).group("text")

        self.assertEqual(
            "H|\\^&||0t4cvJ|Contour7900^02.13\\01.00\\02.40^7901H33A1578|A=0^C=6^R=0^S=0^U=0^V=10600^X=070070180130^a=0^J=0|25|||||P|1|20260208104218|",
            result,
        )

    def test_parse_header_record(self):
        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find("\x02")

        result = contourusb._RECORD_FORMAT.match(header_record_decoded[stx:]).group("text")
        contourusb.ContourHidDevice.parse_header_record(self.mock_dev, result)

        self.assertEqual(self.mock_dev.field_del, "\\")
        self.assertEqual(self.mock_dev.repeat_del, "^")
        self.assertEqual(self.mock_dev.component_del, "&")
        self.assertEqual(self.mock_dev.escape_del, "|")

        self.assertEqual(self.mock_dev.product_code, "Contour7900")

        self.assertEqual(self.mock_dev.dig_ver, "02.13")
        self.assertEqual(self.mock_dev.anlg_ver, "01.00")
        self.assertEqual(self.mock_dev.agp_ver, "02.40")
        self.assertEqual(self.mock_dev.serial_num, "7901H33A1578")

        self.assertEqual(self.mock_dev.res_marking, "0")
        self.assertEqual(self.mock_dev.config_bits, "6")

        self.assertEqual(self.mock_dev.ref_method, "0")
        self.assertEqual(self.mock_dev.internal, "0")
        self.assertEqual(self.mock_dev.unit, "0")
        self.assertEqual(self.mock_dev.lo_bound, "10")
        self.assertEqual(self.mock_dev.hi_bound, "600")

        self.assertEqual(self.mock_dev.post_food_low, "070")
        self.assertEqual(self.mock_dev.pre_food_low, "070")

        self.assertEqual(self.mock_dev.post_food_high, "180")
        self.assertEqual(self.mock_dev.pre_food_high, "130")

        self.assertEqual(self.mock_dev.total, "25")
        self.assertEqual(self.mock_dev.spec_ver, "1")

        self.assertEqual(self.mock_dev.datetime, "20260208104218")

    def test_parse_result_record(self):
        result_record = "R|3|^^^Glucose|126|mg/dL^P||T0||20260125085519"
        result_dict = contourusb.ContourHidDevice.parse_result_record(
            self.mock_dev, result_record
        )

        self.assertEqual(result_dict["record_type"], "R")
        self.assertEqual(result_dict["seq_num"], "3")
        self.assertEqual(result_dict["test_id"], "Glucose")
        self.assertEqual(result_dict["value"], "126")
        self.assertEqual(result_dict["unit"], "mg/dL")
        self.assertEqual(result_dict["ref_method"], "P")
        self.assertEqual(result_dict["markers"], "T0")
        self.assertEqual(result_dict["datetime"], "20260125085519")
