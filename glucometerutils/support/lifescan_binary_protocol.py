# -*- coding: utf-8 -*-
"""Support module for the LifeScan binary protocol.

A number of LifeScan devices use a semi-compatible binary protocol to talk host
and device, which is (vastly) compatible.

This module implements an interface to send and receive these messages.
"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2014-2018, Diego Elio Pettenò'
__license__ = 'MIT'

import construct

from glucometerutils import common
from glucometerutils.support import construct_extras
from glucometerutils.support import lifescan


PACKET = construct.Struct(
    construct.RawCopy(
        construct.Embedded(
            construct.Struct(
                construct.Const(b'\x02'),  # stx
                'length' / construct.Rebuild(
                    construct.Byte, lambda ctx: len(ctx.message) + 6),
                # The following structure is only used by some of the devices.
                'link_control' / construct.BitStruct(
                    construct.Padding(3),
                    'more' / construct.Default(
                        construct.Flag, False),
                    'disconnect' / construct.Default(
                        construct.Flag, False),
                    'acknowledge' / construct.Default(
                        construct.Flag, False),
                    'expect_receive' / construct.Default(
                        construct.Flag, False),
                    'sequence_number' / construct.Default(
                        construct.Flag, False),
                ),
                'message' / construct.Bytes(length=lambda ctx: ctx.length - 6),
                construct.Const(b'\x03'),  # etx
            ),
        ),
    ),
    'checksum' / construct.Checksum(
        construct.Int16ul, lifescan.crc_ccitt, construct.this.data),
)

VERIO_TIMESTAMP = construct_extras.Timestamp(
    construct.Int32ul, epoch=946684800)  # 2010-01-01 00:00

_GLUCOSE_UNIT_MAPPING_TABLE = {
    common.Unit.MG_DL: 0x00,
    common.Unit.MMOL_L: 0x01,
}

GLUCOSE_UNIT = construct.SymmetricMapping(
    construct.Byte, _GLUCOSE_UNIT_MAPPING_TABLE)
