# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common utility functions for LifeScan meters."""

from glucometerutils import exceptions


class MissingChecksum(exceptions.InvalidResponse):
    """The response misses the expected 4-digits checksum."""

    def __init__(self, response: str):
        super(MissingChecksum, self).__init__(
            f"Response is missing checksum: {response}"
        )


class InvalidSerialNumber(exceptions.Error):
    """The serial number is not as expected."""

    def __init__(self, serial_number: str):
        super(InvalidSerialNumber, self).__init__(
            f"Serial number {serial_number} is invalid."
        )


class MalformedCommand(exceptions.InvalidResponse):
    def __init__(self, message: str):
        super(MalformedCommand, self).__init__(f"Malformed command: {message}")


def crc_ccitt(data: bytes) -> int:
    """Calculate the CRC-16-CCITT with LifeScan's common seed.

    Args:
      data: (bytes) the data to calculate the checksum of

    Returns:
      (int) The 16-bit integer value of the CRC-CCITT calculated.

    This function uses the non-default 0xFFFF seed as used by multiple
    LifeScan meters.
    """
    crc = 0xFFFF

    for byte in data:
        crc = (crc >> 8) & 0xFFFF | (crc << 8) & 0xFFFF
        crc ^= byte
        crc ^= (crc & 0xFF) >> 4
        crc ^= (((crc << 8) & 0xFFFF) << 4) & 0xFFFF
        crc ^= (crc & 0xFF) << 5

    return crc & 0xFFFF
