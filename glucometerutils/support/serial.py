# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines and base driver class for serial-based meters.
"""

import logging
from typing import Optional, Text

import serial

from glucometerutils import exceptions


class SerialDevice:
    """A Serial-connected glucometer driver base.

    This class does not implement an actual driver by itself, but provides an
    easier access to the boilerplate code required for pyserial.

    This helper assumes that communication happens on a standard 8n1
    configuration, with variable baudrate and no hardware flow control.

    The actual drivers should set the following parameters:

      BAUDRATE: (int) the speed the serial port should be opened at.
      DEFAULT_CABLE_ID: (string) USB Vendor/Product ID pair, in format
        abcd:abcd, of the default cable for the meter, in case the user
        didn't pass an explicit device driver.

    Optional parameters available:

      TIMEOUT: (float, default: 1) the read timeout in seconds as defined by
        pyserial.

    After initialization, the following attributes can be used by the driver:
      serial_: (serial.Serial) the open Serial object.

    """

    BAUDRATE = None  # type: int
    DEFAULT_CABLE_ID = None  # type: Text

    TIMEOUT = 1  # type: float

    def __init__(self, device):
        # type: (Optional[Text]) -> None
        assert self.BAUDRATE is not None

        if not device and self.DEFAULT_CABLE_ID:
            logging.info(
                'No --device parameter provided, looking for default cable.')
            device = 'hwgrep://' + self.DEFAULT_CABLE_ID

        if not device:
            raise exceptions.CommandLineError(
                'No --device parameter provided, and no default cable known.')

        self.serial_ = serial.serial_for_url(
            device,
            baudrate=self.BAUDRATE,
            timeout=self.TIMEOUT,
            writeTimeout=None,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False, rtscts=False, dsrdtr=False)
