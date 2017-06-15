"""Common routines and base driver class for HID-based meters.
"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2017, Diego Elio Pettenò'
__license__ = 'MIT'

import logging
import os

from glucometerutils import exceptions


class HidDevice(object):
    """A device speaking USB HID protocol driver base.

    This class does not implement an actual driver by itself, but provides an
    easier access to the boilerplate code required for speaking USB HID.

    This helper wraps around an optional dependency on hidapi library: if
    present the driver will auto-detect the device, if not the device path needs
    to be provided and should point to a device implementing Linux's hidraw
    interface.

    The following constants can be set by the actual drivers:

      USB_VENDOR_ID: (int) USB vendor ID for the device.
      USB_PRODUCT_ID: (int) USB product ID for the device.

    If the VID/PID pair is not provided, the driver will require a device path
    to be used.

    Optional parameters available:

      TIMEOUT_MS: (int, default: NOne) the read timeout in milliseconds, used
        for hidapi reads only. If -1, hidapi will be provided no timeout.
    """

    USB_VENDOR_ID = None
    USB_PRODUCT_ID = None

    TIMEOUT_MS = None

    def __init__(self, device):
        if None in (self.USB_VENDOR_ID, self.USB_PRODUCT_ID) and not device:
            raise exceptions.CommandLineError(
                '--device parameter is required, should point to a /dev/hidraw '
                'device node representing the meter.')

        # If the user passed a device path that does not exist, raise an
        # error. This is to avoid writing to a file instead of to a device node.
        if device and not os.path.exists(device):
            raise exceptions.ConnectionFailed(
                message='Path %s does not exist.' % device)

        # If the user passed a device, try opening it.
        if device:
            self.handle_ = open(device, 'w+b')
            self.handle_mode_ = 'hidraw'
        else:
            logging.info(
                'No --device parameter provided, using hidapi library.')
            try:
                import hid
                self.handle_ = hid.device()
                self.handle_.open(self.USB_VENDOR_ID, self.USB_PRODUCT_ID)
                self.handle_mode_ = 'hidapi'
            except ImportError:
                raise exceptions.ConnectionFailed(
                    message='Missing requied "hidapi" module.')
            except OSError as e:
                raise exceptions.ConnectionFailed(
                    message='Unable to connect to meter: %s.' % e)

    def _write(self, report):
        """Writes a report to the HID handle."""

        if self.handle_.write(report) < 0:
            raise exceptions.CommandError()

    def _read(self, size=64):
        """Read a report from the HID handle.

        This is important as it handles the one incompatible interface between
        hidraw devices and hidapi handles.
        """
        if self.handle_mode_ == 'hidraw' or self.TIMEOUT_MS is None:
            return bytes(self.handle_.read(size))
        else:
            return bytes(self.handle_.read(size, timeout_ms=self.TIMEOUT_MS))
