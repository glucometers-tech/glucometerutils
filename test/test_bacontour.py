# -*- coding: utf-8 -*-


"""Tests for the Bayer Contour driver."""

__author__ = 'Alexander Schrijver'
__email__ = 'alex@flupzor.nl'
__copyright__ = 'Copyright © 2017, Alexander Schrijver'
__license__ = 'MIT'


import os
import sys
import unittest
from datetime import datetime
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glucometerutils import exceptions, common
from glucometerutils.drivers import bacontour

from mocks import MockHandle, Operation


class TestBayerContour(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)

        self.handle_mock = MockHandle(padding=b'\x00')
        self.hid_mock = MagicMock()
        self.hid_mock.device.return_value = self.handle_mock
        self.modules_mock = patch.dict('sys.modules', **{'hid': self.hid_mock, }).start()
        self.device = bacontour.Device(None)

    def test__get_lis1a_frame_too_small(self):
        """
        When the header is too small, an exception should be thrown.
        """
        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[b'123', None])
        with self.assertRaises(exceptions.InvalidResponse):
            self.device._read_lis1a_frame()

    def test__get_lis1a_frame_one_block(self):
        """
        This is the normal case when a block is < 64 bytes.
        """
        data = b' ' * 40
        frame = b'ABC' + chr(len(data)).encode('ascii') + data

        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[frame, None])
        read = self.device._read_lis1a_frame()
        self.assertEqual(data, read)
        self.device._read.assert_called_once()

    def test__get_lis1a_frame_two_blocks(self):
        """
        Test the case where there are two blocks which should be read.
        """
        data1 = b' ' * 60
        frame1 = b'ABC' + chr(len(data1)).encode('ascii') + data1
        self.assertEqual(len(frame1), self.device.blocksize)

        data2 = b' ' * 40
        frame2 = b'ABC' + chr(len(data2)).encode('ascii') + data2

        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[frame1, frame2, None])
        read = self.device._read_lis1a_frame()
        self.assertEqual(data1 + data2, read)
        self.assertEqual(self.device._read.call_count, 2)

    def test__read_lis1a_frame_exactly_two_blocks(self):
        """
        Test the case where there are two blocks of _exactly_ 64 bytes.
        """
        data1 = b' ' * 60
        frame1 = b'ABC' + chr(len(data1)).encode('ascii') + data1
        self.assertEqual(len(frame1), self.device.blocksize)

        data2 = b' ' * 60
        frame2 = b'ABC' + chr(len(data2)).encode('ascii') + data2

        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[frame1, frame2, None])
        read = self.device._read_lis1a_frame()
        self.assertEqual(data1 + data2, read)
        self.assertEqual(self.device._read.call_count, 3)

    def test__read_lis1a_frame_nothing(self):
        """
        Test that when no data is read, the method still returns an
        empty byte string.
        """
        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])
        read = self.device._read_lis1a_frame()
        self.assertEqual(read, b'')
        self.device._read.assert_called_once()

    def test__parse_lis1a_intermediate_transfer_frame(self):
        """
        Test parsing of a LIS1A intermediate frame.
        """
        test_frame = b'\x021SOMETEXT\x17C1\r\n'
        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])
        frame_number, is_end_frame, text = self.device._parse_lis1a_transfer_frame(0, test_frame)

        self.assertEqual(frame_number, 1)
        self.assertFalse(is_end_frame)
        self.assertEqual(text, b'SOMETEXT')

    def test__parse_lis1a_end_transfer_frame(self):
        """
        Test parsing of a LIS1A end frame.
        """
        test_frame = b'\x021SOMETEXT\x03AD\r\n'
        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])
        frame_number, is_end_frame, text = self.device._parse_lis1a_transfer_frame(0, test_frame)

        self.assertEqual(frame_number, 1)
        self.assertTrue(is_end_frame)
        self.assertEqual(text, b'SOMETEXT')

    def test__parse_lis1a_invalid_transfer_frame(self):
        """
        Test parsing of a LIS1A end frame with an invalid checksum.
        """
        test_frame = b'\x021SOMETEXT\x0300\r\n'
        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])

        with self.assertRaises(exceptions.InvalidChecksum) as e:
            frame_number, is_end_frame, text = self.device._parse_lis1a_transfer_frame(0, test_frame)

        self.assertEqual(
            str(e.exception),
            'Response checksum not matching: 000000ad expected, 00000000 gotten'
        )

    def test_lis2a2_header_record(self):
        """
        Test if the header record can be parsed properly.

        I'm not entirely sure what all the data means, as reference i've used
        the data that I found in the glucose meter itself.

        Data from my Bayer Contour USB blood glucose meter

        You can find the info by going to 'Setup' then 'Customer Service'
        and then enter '3422' as access code.

        Model: 7390
        Serial 2408612
        SKU: 7397

        Versions: DE: 01.26, AE: 01.05, GP 08.02.20
        """

        frames = iter([
            b'H|\\^&||abcdef|Bayer7390^01.26\\01.05\\08.02.20^7390-2408612^7397-|'
            b'A=1^C=62^G=0^I=0200^R=0^S=1^U=1^V=10600^X=070070070070180130180250^'
            b'Y=360126090050099050300089^Z=1|2000|||||P|1|201708242247',
        ])

        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])
        self.device._parse_lis2a2_message(frames)

        self.assertEqual(self.device.get_serial_number(), '7390-2408612')
        self.assertEqual(self.device.get_version(), 'Bayer7390 DE: 01.26 AE: 01.05 GP: 08.02.20')

    def test_lis2a2_result_records(self):
        """
        Test that result records can be properly processed.
        """
        frames = iter([
            b'H|\^&||NIylNt|Bayer7390^01.26\\01.05\\08.02.20^7390-2408612^7397-|'
            b'A=1^C=62^G=0^I=0200^R=0^S=1^U=1^V=10600^X=070070070070180130180250^'
            b'Y=360126090050099050300089^Z=1|2000|||||P|1|201708290020',
            b'P|1',
            b'R|1|^^^Glucose|8.6|mmol/L^P||A||201608242306',
            b'R|2|^^^Glucose|7.8|mmol/L^P||A||201608251230',
            b'R|3|^^^Glucose|7.8|mmol/L^P||A||201608251833',
            b'L|1||N',
        ])

        self.device._write = Mock(return_value=None)
        self.device._read = Mock(side_effect=[None, None])
        self.device._parse_lis2a2_message(frames)

        readings = self.device.get_readings()
        self.assertEqual(len(readings), 3)

        # Due to rounding in unit conversion a bit of precision is lost.
        self.assertEqual(readings[0].timestamp, datetime(2016, 8, 24, 23, 6))
        self.assertAlmostEqual(readings[0].get_value_as(common.Unit.MMOL_L), 8.6, places=1)

        self.assertEqual(readings[1].timestamp, datetime(2016, 8, 25, 12, 30))
        self.assertAlmostEqual(readings[1].get_value_as(common.Unit.MMOL_L), 7.8, places=1)

        self.assertEqual(readings[2].timestamp, datetime(2016, 8, 25, 18, 33))
        self.assertAlmostEqual(readings[2].get_value_as(common.Unit.MMOL_L), 7.8, places=1)

    def test_integration(self):
        """
        Except for the HID library (which is mocked) test the integration of all the components for
        the bacontour driver.
        """

        operations = [
            # ENQ
            Operation('read', b"ABC\x01\x05"),
            # ACK
            Operation('write', b"ABC\x01\x06"),
            # LIS2a2 headers
            Operation('read', b'ABC<\x021H|\^&||NIylNt|Bayer7390^01.26\\01.05\\08.02.20^7390-2408612^'),
            Operation('read', b'ABC<7397-|A=1^C=62^G=0^I=0200^R=0^S=1^U=1^V=10600^X=070070070070'),
            Operation('read', b'ABC<180130180250^Y=360126090050099050300089^Z=1|2000|||||P|1|201'),
            Operation('read', b'ABC\x0f708222058\r\x17AB\r\n'),
            # LIS2a2 headers ack
            Operation('write', b'ABC\x01\x06'),
            # LIS2a2 patient record
            Operation('read', b'ABC\x0b\x022P|1\r\x1753\r\n'),
            # ACK
            Operation('write', b'ABC\x01\x06'),
            # LIS2a2 results
            Operation('read', b'ABC5\x023R|1|^^^Glucose|10.9|mmol/L^P||A||201504171154\r\x17EC\r\n'),
            Operation('write', b'ABC\x01\x06'),
            Operation('read', b'ABC\x0e\x024L|1||N\r\x0383\r\n'),
            Operation('write', b'ABC\x01\x06'),
            Operation('read', b'ABC\x01\x04'),
        ]
        self.handle_mock.set_operations(operations)

        self.device.connect()

        readings = self.device.get_readings()
        self.assertEqual(len(readings), 1)

        self.assertEqual(self.device.get_serial_number(), '7390-2408612')
        self.assertEqual(self.device.get_version(), 'Bayer7390 DE: 01.26 AE: 01.05 GP: 08.02.20')

        # Due to rounding in unit conversion a bit of precision is lost.
        self.assertEqual(readings[0].timestamp, datetime(2015, 4, 17, 11, 54))
        self.assertAlmostEqual(readings[0].get_value_as(common.Unit.MMOL_L), 10.9, places=1)


if __name__ == '__main__':
    unittest.main()
