# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2018 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Support module for the LifeScan binary protocol.

A number of LifeScan devices use a semi-compatible binary protocol to talk host
and device, which is (vastly) compatible.

This module implements an interface to send and receive these messages.
"""

import construct

from glucometerutils import common
from glucometerutils.support import construct_extras, lifescan

_LINK_CONTROL = construct.BitStruct(
    padding=construct.Padding(3),
    more=construct.Default(construct.Flag, False),
    disconnect=construct.Default(construct.Flag, False),
    acknowledge=construct.Default(construct.Flag, False),
    expect_receive=construct.Default(construct.Flag, False),
    sequence_number=construct.Default(construct.Flag, False),
)


def LifeScanPacket(
    include_link_control: bool,
) -> construct.Struct:  # pylint: disable=invalid-name
    if include_link_control:
        link_control_construct = _LINK_CONTROL
    else:
        link_control_construct = construct.Const(b"\x00")

    return construct.Struct(
        data=construct.RawCopy(
            construct.Struct(
                stx=construct.Const(b"\x02"),
                length=construct.Rebuild(
                    construct.Byte, lambda this: len(this.message) + 6
                ),
                link_control=link_control_construct,
                message=construct.Bytes(lambda this: this.length - 6),
                etx=construct.Const(b"\x03"),
            ),
        ),
        checksum=construct.Checksum(
            construct.Int16ul, lifescan.crc_ccitt, construct.this.data.data
        ),
    )


VERIO_TIMESTAMP = construct_extras.Timestamp(
    construct.Int32ul, epoch=946684800
)  # 2000-01-01 (not 2010)

_GLUCOSE_UNIT_MAPPING_TABLE = {
    common.Unit.MG_DL: 0x00,
    common.Unit.MMOL_L: 0x01,
}

GLUCOSE_UNIT = construct.Mapping(construct.Byte, _GLUCOSE_UNIT_MAPPING_TABLE)
