# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines and base driver class for HID-based meters.
"""

import logging
import os
from typing import BinaryIO, Optional

from glucometerutils import exceptions


class HidSession:
    """An access class to speak to USB HID based devices.

    This class does not implement a full driver, but rather provide simpler read/write
    methods abstracting the HID library.
    """

    handle_: Optional[BinaryIO]

    def __init__(
        self,
        usb_id: Optional[tuple[int, int]],
        device: Optional[str],
        timeout_ms: int = 0,
    ) -> None:
        """Construct a new session object.

        Args:
          usb_id: Optional pair of vendor_id and product_id for the session.
            This is required to use the hidapi library.
          device: Optional path to Linux hidraw-style device path. If not provided,
            usb_id needs to be provided instead.
          timeout_ms: Timeout in milliseconds for read operations. Only relevant when
            using hidapi library.
        """

        self._timeout_ms = timeout_ms

        if not usb_id and not device:
            raise exceptions.CommandLineError(
                "--device parameter is required, should point to a /dev/hidraw "
                "device node representing the meter."
            )

        # If the user passed a device path that does not exist, raise an
        # error. This is to avoid writing to a file instead of to a device node.
        if device and not os.path.exists(device):
            raise exceptions.ConnectionFailed(message=f"Path {device} does not exist.")

        # If the user passed a device, try opening it.
        if device:
            self.handle_ = open(device, "w+b")
        else:
            self.handle_ = None
            logging.info("No --device parameter provided, using hidapi library.")
            try:
                import hid

                assert usb_id
                vendor_id, product_id = usb_id
                self.hidapi_handle_ = hid.device()
                self.hidapi_handle_.open(vendor_id, product_id)
            except ImportError:
                raise exceptions.ConnectionFailed(
                    message='Missing requied "hidapi" module.'
                )
            except OSError as e:
                raise exceptions.ConnectionFailed(
                    message=f"Unable to connect to meter: {e}."
                )

    def write(self, report: bytes) -> None:
        """Writes a report to the HID handle."""

        if self.handle_:
            written = self.handle_.write(report)
        else:
            written = self.hidapi_handle_.write(report)

        if written < 0:
            raise exceptions.CommandError()

    def read(self, size: int = 64) -> bytes:
        """Read a report from the HID handle.

        This is important as it handles the one incompatible interface between
        hidraw devices and hidapi handles.
        """
        if self.handle_:
            return bytes(self.handle_.read(size))

        return bytes(self.hidapi_handle_.read(size, timeout_ms=self._timeout_ms))
