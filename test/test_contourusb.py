# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the common ContourUSB functions.."""

# pylint: disable=protected-access,missing-docstring

from absl.testing import absltest

from glucometerutils.support import contourusb

from unittest.mock import Mock



class TestContourUSB(absltest.TestCase):

    header_record = b'\x04\x021H|\\^&||7w3LBL|Bayer7390^01.24\\01.04\\09.02.20^7390-2336773^7403-|A=1^C=63^G=1^I=0200^R=0^S=1^U=0^V=10600^X=070070070070180130150250^Y=360126090050099050300089^Z=1|1714||||||1|201909221304\r\x17D7\r\n\x05'
    
    mock_dev = Mock()

    def test_get_datetime(self):
        import datetime

        self.datetime = "201908071315" # returned by 
        self.assertEqual(
            datetime.datetime(2019,8,7,13,15),
            contourusb.ContourHidDevice.get_datetime(self)
        )

    
    def test_RECORD_FORMAT_match(self):
        #first decode the header record frame
        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find('\x02')

        _RECORD_FORMAT = contourusb._RECORD_FORMAT
        result = _RECORD_FORMAT.match(header_record_decoded[stx:]).group('text')

        self.assertEqual(
    	   "H|\\^&||7w3LBL|Bayer7390^01.24\\01.04\\09.02.20^7390-2336773^7403-|A=1^C=63^G=1^I=0200^R=0^S=1^U=0^V=10600^X=070070070070180130150250^Y=360126090050099050300089^Z=1|1714||||||1|201909221304",
            result
        )

    def test_parse_header_record(self):
        
        _HEADER_RECORD_RE = contourusb._HEADER_RECORD_RE
        _RECORD_FORMAT = contourusb._RECORD_FORMAT


        header_record_decoded = self.header_record.decode()
        stx = header_record_decoded.find('\x02')


        result = _RECORD_FORMAT.match(header_record_decoded[stx:]).group('text')
        contourusb.ContourHidDevice.parse_header_record(self.mock_dev,result)

        self.assertEqual(self.mock_dev.field_del, "\\")
        self.assertEqual(self.mock_dev.repeat_del, "^")
        self.assertEqual(self.mock_dev.component_del, "&")
        self.assertEqual(self.mock_dev.escape_del, "|")

        self.assertEqual(self.mock_dev.product_code, "Bayer7390")        

        self.assertEqual(self.mock_dev.dig_ver, "01.24")
        self.assertEqual(self.mock_dev.anlg_ver, "01.04")
        self.assertEqual(self.mock_dev.agp_ver, "09.02.20")
        self.assertEqual(self.mock_dev.serial_num, "7390-2336773")
        self.assertEqual(self.mock_dev.sku_id, "7403-")
        self.assertEqual(self.mock_dev.res_marking, "1")
        self.assertEqual(self.mock_dev.config_bits, "63")
        self.assertEqual(self.mock_dev.lang, "1")
        self.assertEqual(self.mock_dev.interv, "0200")
        self.assertEqual(self.mock_dev.ref_method, "0")
        self.assertEqual(self.mock_dev.internal, "1")
        self.assertEqual(self.mock_dev.unit, "0")
        self.assertEqual(self.mock_dev.lo_bound, "10")
        self.assertEqual(self.mock_dev.hi_bound, "600")

        self.assertEqual(self.mock_dev.hypo_limit, "070")
        self.assertEqual(self.mock_dev.overall_low, "070")
        self.assertEqual(self.mock_dev.pre_food_low, "070")
        self.assertEqual(self.mock_dev.post_food_low, "070")
        self.assertEqual(self.mock_dev.overall_high, "180")
        self.assertEqual(self.mock_dev.pre_food_high, "130")
        self.assertEqual(self.mock_dev.post_food_high, "150")
        self.assertEqual(self.mock_dev.hyper_limit, "250")

        self.assertEqual(self.mock_dev.upp_hyper, "360")
        self.assertEqual(self.mock_dev.low_hyper, "126")
        self.assertEqual(self.mock_dev.upp_hypo, "090")
        self.assertEqual(self.mock_dev.low_hypo, "050")
        self.assertEqual(self.mock_dev.upp_low_target, "099")
        self.assertEqual(self.mock_dev.low_low_target, "050")
        self.assertEqual(self.mock_dev.upp_hi_target, "300")
        self.assertEqual(self.mock_dev.low_hi_target, "089")
        self.assertEqual(self.mock_dev.trends, "1")
        self.assertEqual(self.mock_dev.total, "1714")
        self.assertEqual(self.mock_dev.spec_ver, "1")

        self.assertEqual(self.mock_dev.datetime, "201909221304")

    #TO-DO checksum and checkframe unit tests

    def test_parse_result_record(self):
        #first decode the header record frame
        result_record = "R|8|^^^Glucose|133|mg/dL^P||B/X||201202052034"
        result_dict = contourusb.ContourHidDevice.parse_result_record(self.mock_dev, result_record)

        self.assertEqual(result_dict['record_type'], 'R')
        self.assertEqual(result_dict['seq_num'], '8')
        self.assertEqual(result_dict['test_id'], 'Glucose')
        self.assertEqual(result_dict['value'], '133')
        self.assertEqual(result_dict['unit'], 'mg/dL')
        self.assertEqual(result_dict['ref_method'], 'P')
        self.assertEqual(result_dict['markers'], 'B/X')
        self.assertEqual(result_dict['datetime'], '201202052034')