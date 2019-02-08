# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines to implement the FreeStyle common protocol.

Protocol documentation available at
https://flameeyes.github.io/glucometer-protocols/abbott/shared-hid-protocol.html

"""

import csv
import datetime
import logging
import re

try:
    from typing import Iterator, List, Text, Tuple
except ImportError:
    pass

import construct

from glucometerutils import exceptions
from glucometerutils.support import hiddevice

# Sequence of initialization messages sent to the device to establish HID
# protocol.
_INIT_SEQUENCE = (0x04, 0x05, 0x15, 0x01)

_FREESTYLE_MESSAGE = construct.Struct(
    'hid_report' / construct.Const(0, construct.Byte),
    'message_type' / construct.Byte,
    'command' / construct.Padded(
        63,  # command can only be up to 62 bytes, but one is used for length.
        construct.Prefixed(construct.Byte, construct.GreedyBytes)),
)

_TEXT_COMPLETION_RE = re.compile('CMD (?:OK|Fail!)')
_TEXT_REPLY_FORMAT = re.compile(
    '^(?P<message>.*)CKSM:(?P<checksum>[0-9A-F]{8})\r\n'
    'CMD (?P<status>OK|Fail!)\r\n$', re.DOTALL)

_MULTIRECORDS_FORMAT = re.compile(
    '^(?P<message>.+\r\n)(?P<count>[0-9]+),(?P<checksum>[0-9A-F]{8})\r\n$',
    re.DOTALL)


def _verify_checksum(message, expected_checksum_hex):
    # type: (Text, Text) -> None
    """Calculate the simple checksum of the message and compare with expected.

    Args:
      message: (str) message to calculate the checksum of.
      expected_checksum_hex: (str) hexadecimal string representing the checksum
        expected to match the message.

    Raises:
      InvalidChecksum: if the message checksum calculated does not match the one
        received.
    """
    expected_checksum = int(expected_checksum_hex, 16)
    calculated_checksum = sum(ord(c) for c in message)

    if expected_checksum != calculated_checksum:
        raise exceptions.InvalidChecksum(expected_checksum, calculated_checksum)


class FreeStyleHidDevice(hiddevice.HidDevice):
    """Base class implementing the FreeStyle HID common protocol.

    This class implements opening, initializing the connection and sending
    commands to the device, reading the response and confirming the checksums.

    Commands sent to the devices over this protocol have a "message type"
    prefixed to the command itself. Text command are usually sent with message
    type 0x60, and the replied received with the same. Some devices may diverge
    though.
    """

    TEXT_CMD = 0x60
    TEXT_REPLY_CMD = 0x60

    USB_VENDOR_ID = 0x1a61  # type: int  # Abbott Diabetes Care
    USB_PRODUCT_ID = None  # type: int

    def connect(self):
        """Open connection to the device, starting the knocking sequence."""
        for message in _INIT_SEQUENCE:
            self._send_command(message, b'')
            # Ignore the returned values, they are not generally useful. The
            # Serial Number as returned may not actually match the device's
            # serial number (e.g. in the FreeStyle Precision Neo).
            self._read_response()

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

    def _send_command(self, message_type, command):
        # type: (int, bytes) -> None
        """Send a raw command to the device.

        Args:
          message_type: (int) The first byte sent with the report to the device.
          command: (bytes) The command to send out the device.
        """
        usb_packet = _FREESTYLE_MESSAGE.build(
            {'message_type': message_type, 'command': command})

        logging.debug('Sending packet: %r', usb_packet)
        self._write(usb_packet)

    def _read_response(self):
        # type: () -> Tuple[int, bytes]
        """Read the response from the device and extracts it."""
        usb_packet = self._read()

        logging.debug('Read packet: %r', usb_packet)

        assert usb_packet
        message_type = usb_packet[0]
        message_length = usb_packet[1]
        message_content = usb_packet[2:2+message_length]

        # There appears to be a stray number of 22 01 xx messages being returned
        # by some devices after commands are sent. These do not appear to have
        # meaning, so ignore them and proceed to the next.
        if message_type == 0x22 and message_length == 1:
            return self._read_response()

        # hidapi module returns a list of bytes rather than a bytes object.
        return (message_type, bytes(message_content))

    def _send_text_command(self, command):
        # type: (bytes) -> Text
        """Send a command to the device that expects a text reply."""
        self._send_command(self.TEXT_CMD, command)

        # Reply can stretch multiple buffers
        full_content = ''
        while True:
            message_type, content = self._read_response()

            if message_type != self.TEXT_REPLY_CMD:
                raise exceptions.InvalidResponse(
                    'Message type %02x does not match expectations: %s' %
                    (message_type, content.decode('ascii')))

            full_content += content.decode('ascii')

            if _TEXT_COMPLETION_RE.search(full_content):
                break

        match = _TEXT_REPLY_FORMAT.search(full_content)
        if not match:
            raise exceptions.InvalidResponse(full_content)

        message = match.group('message')
        _verify_checksum(message, match.group('checksum'))

        if match.group('status') != 'OK':
            raise exceptions.InvalidResponse(message or "Command failed")

        return message

    # Some of the commands are also shared across devices that use this HID
    # protocol, but not many. Only provide here those that do seep to change
    # between them.
    def _get_version(self):
        # type: () -> Text
        """Return the software version of the device."""
        return self._send_text_command(b'$swver?').rstrip('\r\n')

    def get_serial_number(self):
        # type: () -> Text
        """Returns the serial number of the device."""
        return self._send_text_command(b'$serlnum?').rstrip('\r\n')

    def get_datetime(self):
        # type: () -> datetime.datetime
        """Gets the date and time as reported by the device.

        This is one of the few commands that appear common to many of the
        FreeStyle devices that use the HID framing protocol.
        """
        date = self._send_text_command(b'$date?').rstrip('\r\n')
        time = self._send_text_command(b'$time?').rstrip('\r\n')

        # Year is returned as an offset to 2000.
        month, day, year = (int(x) for x in date.split(','))
        hour, minute = (int(x) for x in time.split(','))

        return datetime.datetime(year + 2000, month, day, hour, minute)

    def set_datetime(self, date=datetime.datetime.now()):
        # type: (datetime.datetime) -> datetime.datetime
        """Sets the date and time of the device."""

        # The format used by the FreeStyle devices is not composable based on
        # standard strftime() (namely it includes no leading zeros), so we need
        # to build it manually.
        date_cmd = '$date,{month},{day},{year}'.format(
            month=date.month, day=date.day, year=(date.year-2000))
        time_cmd = '$time,{hour},{minute}'.format(
            hour=date.hour, minute=date.minute)

        self._send_text_command(bytes(date_cmd, "ascii"))
        self._send_text_command(bytes(time_cmd, "ascii"))

        return self.get_datetime()

    def zero_log(self):
        """Not implemented, Abbott devices don't allow resetting memory."""
        raise NotImplementedError

    def _get_multirecord(self, command):
        # type: (bytes) -> Iterator[List[Text]]
        """Queries for, and returns, "multirecords" results.

        Multirecords are used for querying events, readings, history and similar
        other data out of a FreeStyle device. These are comma-separated values,
        variable-length.

        The validation includes the general HID framing parsing, as well as
        validation of the record count, and of the embedded records checksum.

        Args:
          command: (bytes) the text command to send to the device for the query.

        Returns:
          (csv.reader): a CSV reader object that returns a record for each line
             in the record file.
        """
        message = self._send_text_command(command)
        match = _MULTIRECORDS_FORMAT.search(message)
        if not match:
            raise exceptions.InvalidResponse(message)

        records_str = match.group('message')
        _verify_checksum(records_str, match.group('checksum'))

        logging.debug('Received multi-record string: %s', records_str)

        return csv.reader(records_str.split('\r\n'))
