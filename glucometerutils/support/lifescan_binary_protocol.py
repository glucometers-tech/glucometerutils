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

def LifeScanPacket(include_link_control):
    # type: (bool) -> construct.Struct
    if include_link_control:
        link_control_construct = _LINK_CONTROL
    else:
        link_control_construct = construct.Const(b'\x00')

    return construct.Struct(
        'data' / construct.RawCopy(
                construct.Struct(
                    construct.Const(b'\x02'),  # stx
                    'length' / construct.Rebuild(
                        construct.Byte, lambda this: len(this.message) + 6),
                    'link_control' / link_control_construct,
                    'message' / construct.Bytes(
                        lambda this: this.length - 6),
                    construct.Const(b'\x03'),  # etx
                ),
        ),
        'checksum' / construct.Checksum(
            construct.Int16ul, lifescan.crc_ccitt, construct.this.data.data),
    )

VERIO_TIMESTAMP = construct_extras.Timestamp(
    construct.Int32ul, epoch=946684800)  # 2000-01-01 (not 2010)

_GLUCOSE_UNIT_MAPPING_TABLE = {
    common.Unit.MG_DL: 0x00,
    common.Unit.MMOL_L: 0x01,
}

GLUCOSE_UNIT = construct.Mapping(
    construct.Byte, _GLUCOSE_UNIT_MAPPING_TABLE)
