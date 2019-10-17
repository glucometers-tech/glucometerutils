# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the common ContourUSB functions.."""

# pylint: disable=protected-access,missing-docstring

from absl.testing import absltest

from glucometerutils.drivers import contournextone

from unittest.mock import Mock

class TestContourNextOne(absltest.TestCase):

    header_record = b'\x04\x021H|\\^&||7yMyBR|Contour7800^01.16\\02.00\\20.35^7801-1417178|A=1^C=7^R=0^S=1^U=0^V=10600^X=070070180130^a=1^J=0|2|||||P|1|20191017205106|\r\x17D7\r\n\x05'
    
    mock_dev = Mock()
    mock_dev = contournextone.Device

    def test_get_datetime(self):
        import datetime

        self.datetime = "201908071315" # returned by 
        self.assertEqual(
            datetime.datetime(2019,8,7,13,15),
            self.mock_dev.get_datetime(self)
        )

    
    def test_RECORD_FORMAT_match(self):
        #first decode the header record frame
        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find('\x02')

        _RECORD_FORMAT = self.mock_dev._RECORD_FORMAT
        result = _RECORD_FORMAT.match(header_record_decoded[stx:]).group('text')

        self.assertEqual(
    	   "H|\\^&||7yMyBR|Contour7800^01.16\\02.00\\20.35^7801-1417178|A=1^C=7^R=0^S=1^U=0^V=10600^X=070070180130^a=1^J=0|2|||||P|1|20191017205106|",
            result
        )

    def test_parse_header_record(self):
        _HEADER_RECORD_RE = self.mock_dev._HEADER_RECORD_RE
        _RECORD_FORMAT = self.mock_dev._RECORD_FORMAT

        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find('\x02')

        result = _RECORD_FORMAT.match(header_record_decoded[stx:]).group('text')
        self.mock_dev.parse_header_record(self.mock_dev,result)

        self.assertEqual(self.mock_dev.field_del, "\\")
        self.assertEqual(self.mock_dev.repeat_del, "^")
        self.assertEqual(self.mock_dev.component_del, "&")
        self.assertEqual(self.mock_dev.escape_del, "|")

        self.assertEqual(self.mock_dev.product_code, "Contour7800")        
        self.assertEqual(self.mock_dev.dig_ver, "01.16")
        self.assertEqual(self.mock_dev.alg_ver, "02.00")
        self.assertEqual(self.mock_dev.rfe_ver, "20.35")

        self.assertEqual(self.mock_dev.serial_num, "7801-1417178")
        self.assertEqual(self.mock_dev.res_marking, "1")
        self.assertEqual(self.mock_dev.config_bits, "7")
        self.assertEqual(self.mock_dev.ref_method, "0")

        self.assertEqual(self.mock_dev.unit, "0")
        self.assertEqual(self.mock_dev.lo_bound, "10")
        self.assertEqual(self.mock_dev.hi_bound, "600")

        self.assertEqual(self.mock_dev.post_lo, "070")
        self.assertEqual(self.mock_dev.fasting_lo, "070")
        self.assertEqual(self.mock_dev.post_hi, "180")
        self.assertEqual(self.mock_dev.fasting_hi, "130")
        
        self.assertEqual(self.mock_dev.target_ind, "1")
        self.assertEqual(self.mock_dev.sensor_type, "0")
        
        self.assertEqual(self.mock_dev.total, "2")
        
        self.assertEqual(self.mock_dev.datetime, "20191017205106")

    #TO-DO checksum and checkframe unit tests

    def test_parse_result_record(self):
        #first decode the header record frame
        result_record = "R|2|^^^Glucose|159|mg/dL^P||T0/M0||20191016001203"
        result_dict = self.mock_dev.parse_result_record(self.mock_dev, result_record)

        self.assertEqual(result_dict['record_type'], 'R')
        self.assertEqual(result_dict['seq_num'], '2')
        self.assertEqual(result_dict['test_id'], 'Glucose')
        self.assertEqual(result_dict['value'], '159')
        self.assertEqual(result_dict['unit'], 'mg/dL')
        self.assertEqual(result_dict['ref_method'], 'P')
        self.assertEqual(result_dict['markers'], 'T0/M0')
        self.assertEqual(result_dict['datetime'], '20191016001203')

    def test_parse_message_terminator_record(self):
        #first decode the header record frame
        result_record = "L|1||N"

        _MESSAGE_TERMINATOR_RECORD_RE = self.mock_dev._MESSAGE_TERMINATOR_RECORD_RE
        self.assertTrue(_MESSAGE_TERMINATOR_RECORD_RE.match(result_record))