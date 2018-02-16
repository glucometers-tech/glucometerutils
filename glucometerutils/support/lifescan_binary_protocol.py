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

_LINK_CONTROL = construct.BitStruct(
    construct.Padding(3),
    'more' / construct.Default(construct.Flag, False),
    'disconnect' / construct.Default(construct.Flag, False),
    'acknowledge' / construct.Default(construct.Flag, False),
    'expect_receive' / construct.Default(construct.Flag, False),
    'sequence_number' / construct.Default(construct.Flag, False),
)

def LifeScanPacket(command_prefix, include_link_control):
    if include_link_control:
        link_control_construct = _LINK_CONTROL
    else:
        link_control_construct = construct.Const(b'\x00')

    command_prefix_construct = construct.Const(command_prefix, construct.Byte)

    return construct.Struct(
        construct.RawCopy(
            construct.Embedded(
                construct.Struct(
                    construct.Const(b'\x02'),  # stx
                    'length' / construct.Rebuild(
                        construct.Byte, lambda ctx: len(ctx.message) + 7),
                    'link_control' / link_control_construct,
                    'command_prefix' / command_prefix_construct,
                    'message' / construct.Bytes(
                        length=lambda ctx: ctx.length - 7),
                    construct.Const(b'\x03'),  # etx
                ),
            ),
        ),
        'checksum' / construct.Checksum(
            construct.Int16ul, lifescan.crc_ccitt, construct.this.data),
    )

COMMAND_SUCCESS = construct.Const(b'\x06')

VERIO_TIMESTAMP = construct_extras.Timestamp(
    construct.Int32ul, epoch=946684800)  # 2010-01-01 00:00

_GLUCOSE_UNIT_MAPPING_TABLE = {
    common.Unit.MG_DL: 0x00,
    common.Unit.MMOL_L: 0x01,
}

GLUCOSE_UNIT = construct.SymmetricMapping(
    construct.Byte, _GLUCOSE_UNIT_MAPPING_TABLE)
