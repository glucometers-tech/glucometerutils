# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Tests for the common FreeStyle functions.."""

# pylint: disable=protected-access,missing-docstring

from absl.testing import absltest

from glucometerutils.support import freestyle


class TestFreeStyle(absltest.TestCase):

    def test_outgoing_command(self):
        """Test the generation of a new outgoing message."""

        self.assertEqual(
            b'\0\x17\7command\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0'
            b'\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0',
            freestyle._FREESTYLE_MESSAGE.build(
                {'message_type': 23, 'command': b'command'}),
        )
