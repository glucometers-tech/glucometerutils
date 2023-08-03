# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines to implement the FreeStyle common protocol.

Protocol documentation available at
https://protocols.glucometers.tech/abbott/shared-hid-protocol

"""

import datetime
import pathlib
from typing import Optional

import freestyle_hid

from glucometerutils import driver, exceptions


def convert_ketone_unit(raw_value: float) -> float:
    """Convert raw ketone value as read in the device to its value in mmol/L.

    As per https://protocols.glucometers.tech/abbott/freestyle-libre this is
    actually not using any mg/dL→mmol/L conversion, but rather the same as the
    meter uses for blood glucose.

    """
    return raw_value / 18.0


ABBOTT_VENDOR_ID = 0x1A61


class FreeStyleHidDevice(driver.GlucometerDevice):
    """Base class implementing the FreeStyle HID common protocol.

    This class implements opening, initializing the connection and sending
    commands to the device, reading the response and confirming the checksums.

    Commands sent to the devices over this protocol have a "message type"
    prefixed to the command itself. Text command are usually sent with message
    type 0x60, and the replied received with the same. Some devices may diverge
    though.
    """

    def __init__(
        self,
        product_id: int,
        device_path: Optional[str],
        text_cmd: int = 0x60,
        text_reply_cmd: int = 0x60,
        encoding: str = "ascii",
        encrypted: bool = False,
    ) -> None:
        super().__init__(device_path)
        self._encoding = encoding
        try:
            self._session = freestyle_hid.Session(
                product_id,
                pathlib.Path(device_path) if device_path else None,
                text_cmd,
                text_reply_cmd,
                encoding=encoding,
                encrypted=encrypted,
            )
        except Exception as e:
            raise exceptions.ConnectionFailed(str(e)) from e

    def connect(self) -> None:
        """Open connection to the device, starting the knocking sequence."""
        try:
            self._session.connect()
        except Exception as e:
            raise exceptions.ConnectionFailed(str(e))

    def disconnect(self) -> None:
        """Disconnect the device, nothing to be done."""
        pass

    # Some of the commands are also shared across devices that use this HID
    # protocol, but not many. Only provide here those that do seep to change
    # between them.
    def _get_version(self) -> str:
        """Return the software version of the device."""
        return self._session.send_text_command(b"$swver?").rstrip("\r\n")

    def get_serial_number(self) -> str:
        """Returns the serial number of the device."""
        return self._session.send_text_command(b"$serlnum?").rstrip("\r\n")

    def get_patient_name(self) -> Optional[str]:
        patient_name = self._session.send_text_command(b"$ptname?").rstrip("\r\n")
        if not patient_name:
            return None
        return patient_name

    def set_patient_name(self, name: str) -> None:
        try:
            encoded_name = name.encode(self._encoding)
        except UnicodeDecodeError as error:
            raise ValueError(
                f"Error encoding patient name to {self._encoding}."
            ) from error

        self._session.send_text_command(b"$ptname," + encoded_name)

    def get_datetime(self) -> datetime.datetime:
        """Gets the date and time as reported by the device.

        This is one of the few commands that appear common to many of the
        FreeStyle devices that use the HID framing protocol.
        """
        date = self._session.send_text_command(b"$date?").rstrip("\r\n")
        time = self._session.send_text_command(b"$time?").rstrip("\r\n")

        # Year is returned as an offset to 2000.
        month, day, year = (int(x) for x in date.split(","))
        hour, minute = (int(x) for x in time.split(","))

        # At least Precision Neo devices can have an invalid date (bad RTC?),
        # and report 255 for each field, which is not valid for
        # datetime.datetime().
        try:
            return datetime.datetime(year + 2000, month, day, hour, minute)
        except ValueError:
            raise exceptions.InvalidDateTime()

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        # The format used by the FreeStyle devices is not composable based on
        # standard strftime() (namely it includes no leading zeros), so we need
        # to build it manually.
        date_cmd = f"$date,{date.month},{date.day},{date.year - 2000}"
        time_cmd = f"$time,{date.hour},{date.minute}"

        self._session.send_text_command(bytes(date_cmd, "ascii"))
        self._session.send_text_command(bytes(time_cmd, "ascii"))

        return self.get_datetime()
