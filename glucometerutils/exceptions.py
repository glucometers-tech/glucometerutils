# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common exceptions for glucometerutils."""

from typing import Any, Optional


class Error(Exception):
    """Base class for the errors."""


class CommandLineError(Error):
    """Error with commandline parameters provided."""


class ConnectionFailed(Error):
    """It was not possible to connect to the meter."""

    def __init__(self, message: str = "Unable to connect to the meter.") -> None:
        super().__init__(message)


class CommandError(Error):
    """It was not possible to send a command to the device."""

    def __init__(self, message: str = "Unable to send command to device.") -> None:
        super().__init__(message)


class InvalidResponse(Error):
    """The response received from the meter was not understood"""

    def __init__(self, response: str) -> None:
        super().__init__(f"Invalid response received:\n{response}")


class InvalidChecksum(InvalidResponse):
    def __init__(self, wire: int, calculated: Optional[int]) -> None:
        if calculated is not None:
            message = f"Response checksum not matching: {wire:08x} (wire) != {calculated:08x} (calculated)"
        else:
            message = f"Unable to calculate checksum. Expected {wire:08x}."

        super().__init__(message)


class InvalidGlucoseUnit(Error):
    """Unable to parse the given glucose unit"""

    def __init__(self, unit: Any) -> None:
        super().__init__(f"Invalid glucose unit received:\n{unit}")


class InvalidDateTime(Error):
    """The device has an invalid date/time setting."""

    def __init__(self) -> None:
        super().__init__("Invalid date and time for device")
