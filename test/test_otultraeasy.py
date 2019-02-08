# -*- coding: utf-8 -*-
"""Tests for the LifeScan OneTouch Ultra Easy driver."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.com'
__copyright__ = 'Copyright © 2018, Diego Elio Pettenò'
__license__ = 'MIT'

# pylint: disable=protected-access,missing-docstring

from absl.testing import absltest

from glucometerutils.drivers import otultraeasy


class ConstructTest(absltest.TestCase):

    def test_make_packet_ack(self):
        self.assertEqual(
            b'\x02\x06\x08\x03\xc2\x62',
            otultraeasy._make_packet(b'', False, False, False, True))

    def test_make_packet_version_request(self):
        self.assertEqual(
            b'\x02\x09\x03\x05\x0d\x02\x03\x08\x9f',
            otultraeasy._make_packet(
                b'\x05\x0d\x02', True, True, False, False))
