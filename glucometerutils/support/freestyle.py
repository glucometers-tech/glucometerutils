# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines to implement the FreeStyle common protocol.

Protocol documentation available at
https://protocols.glucometers.tech/abbott/shared-hid-protocol

"""

import csv
import datetime
import logging
import re
from typing import AnyStr, Callable, Iterator, List, Optional, Text, Tuple

import construct

from glucometerutils import exceptions
from glucometerutils.support import hiddevice

_INIT_COMMAND = 0x01
_INIT_RESPONSE = 0x71

_KEEPALIVE_RESPONSE = 0x22
_UNKNOWN_MESSAGE_RESPONSE = 0x30

_ENCRYPTION_SETUP_COMMAND = 0x14
_ENCRYPTION_SETUP_RESPONSE = 0x33

_ALWAYS_UNENCRYPTED_MESSAGES = (
    _INIT_COMMAND, 0x04, 0x05, 0x06, 0x0c, 0x0d,
    _ENCRYPTION_SETUP_COMMAND, 0x15,
    _ENCRYPTION_SETUP_RESPONSE, 0x34, 0x35,
    _INIT_RESPONSE,
    _KEEPALIVE_RESPONSE,
)

def _create_matcher(message_type, content):
    # type: (int, Optional[bytes]) -> Callable[[Tuple[int, bytes]], bool]
    def _matcher(message):
        return (
            message[0] == message_type and
            (content is None or content == message[1]))

    return _matcher

_is_init_reply = _create_matcher(_INIT_RESPONSE, b'\x01')
_is_keepalive_response = _create_matcher(_KEEPALIVE_RESPONSE, b'\x05')
_is_uknown_message_error = _create_matcher(_UNKNOWN_MESSAGE_RESPONSE, b'\x85')
_is_encryption_missing_error = _create_matcher(
    _ENCRYPTION_SETUP_RESPONSE, b'\x15')
_is_encryption_setup_error = _create_matcher(
    _ENCRYPTION_SETUP_RESPONSE, b'\x14')

_FREESTYLE_MESSAGE = construct.Struct(
    'hid_report' / construct.Const(0, construct.Byte),
    'message_type' / construct.Byte,
    'command' / construct.Padded(
        63,  # command can only be up to 62 bytes, but one is used for length.
        construct.Prefixed(construct.Byte, construct.GreedyBytes)),
)

_FREESTYLE_ENCRYPTED_MESSAGE = construct.Struct(
    'hid_report' / construct.Const(0, construct.Byte),
    'message_type' / construct.Byte,
    'command' / construct.Padded(
        63,  # command can only be up to 62 bytes, but one is used for length.
        construct.GreedyBytes),
)

_TEXT_COMPLETION_RE = re.compile(b'CMD (?:OK|Fail!)')
_TEXT_REPLY_FORMAT = re.compile(
    b'^(?P<message>.*)CKSM:(?P<checksum>[0-9A-F]{8})\r\n'
    b'CMD (?P<status>OK|Fail!)\r\n$', re.DOTALL)

_MULTIRECORDS_FORMAT = re.compile(
    '^(?P<message>.+\r\n)(?P<count>[0-9]+),(?P<checksum>[0-9A-F]{8})\r\n$',
    re.DOTALL)


def _verify_checksum(message, expected_checksum_hex):
    # type: (AnyStr, AnyStr) -> None
    """Calculate the simple checksum of the message and compare with expected.

    Args:
      message: (str) message to calculate the checksum of.
      expected_checksum_hex: hexadecimal string representing the checksum
        expected to match the message.

    Raises:
      InvalidChecksum: if the message checksum calculated does not match the one
        received.
    """
    expected_checksum = int(expected_checksum_hex, 16)
    if isinstance(message, bytes):
        all_bytes = (c for c in message)
    else:
        all_bytes = (ord(c) for c in message)

    calculated_checksum = sum(all_bytes)

    if expected_checksum != calculated_checksum:
        raise exceptions.InvalidChecksum(expected_checksum, calculated_checksum)

def convert_ketone_unit(raw_value):
    """Convert raw ketone value as read in the device to its value in mmol/L.

    As per https://protocols.glucometers.tech/abbott/freestyle-libre this is
    actually not using any mg/dL→mmol/L conversion, but rather the same as the
    meter uses for blood glucose.

    """
    return raw_value / 18.0

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
        self._send_command(_INIT_COMMAND, b'')
        response = self._read_response()
        if not _is_init_reply(response):
            raise exceptions.ConnectionFailed(
                'Connection error: unexpected message %02x:%s' % (
                    response[0], response[1].hex()))

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

    def _send_command(self, message_type, command, encrypted=False):
        # type: (int, bytes, bool) -> None
        """Send a raw command to the device.

        Args:
          message_type: (int) The first byte sent with the report to the device.
          command: (bytes) The command to send out the device.
        """
        if encrypted:
            assert message_type not in _ALWAYS_UNENCRYPTED_MESSAGES
            meta_construct = _FREESTYLE_ENCRYPTED_MESSAGE
        else:
            meta_construct = _FREESTYLE_MESSAGE

        usb_packet = meta_construct.build(
            {'message_type': message_type, 'command': command})

        logging.debug('Sending packet: %r', usb_packet)
        self._write(usb_packet)

    def _read_response(self, encrypted=False):
        # type: (bool) -> Tuple[int, bytes]
        """Read the response from the device and extracts it."""
        usb_packet = self._read()

        logging.debug('Read packet: %r', usb_packet)

        assert usb_packet
        message_type = usb_packet[0]

        if not encrypted or message_type in _ALWAYS_UNENCRYPTED_MESSAGES:
            message_length = usb_packet[1]
            message_content = usb_packet[2:2+message_length]
        else:
            message_content = usb_packet[1:]

        # hidapi module returns a list of bytes rather than a bytes object.
        message = (message_type, bytes(message_content))

        # There appears to be a stray number of 22 01 xx messages being returned
        # by some devices after commands are sent. These do not appear to have
        # meaning, so ignore them and proceed to the next. These are always sent
        # unencrypted, so we need to inspect them before we decide what the
        # message content is.
        if _is_keepalive_response(message):
            return self._read_response(encrypted=encrypted)

        if _is_uknown_message_error(message):
            raise exceptions.CommandError('Invalid command')

        if _is_encryption_missing_error(message):
            raise exceptions.CommandError(
                'Device encryption not initialized.')

        if _is_encryption_setup_error(message):
            raise exceptions.CommandError(
                'Device encryption initialization failed.')

        return message

    def _send_text_command(self, command):
        # type: (bytes) -> Text
        """Send a command to the device that expects a text reply."""
        self._send_command(self.TEXT_CMD, command)

        # Reply can stretch multiple buffers
        full_content = b''
        while True:
            message_type, content = self._read_response()

            logging.debug(
                'Received message: type %02x content %s',
                message_type, content.hex())

            if message_type != self.TEXT_REPLY_CMD:
                raise exceptions.InvalidResponse(
                    'Message type %02x does not match expectations: %r' %
                    (message_type, content))

            full_content += content

            if _TEXT_COMPLETION_RE.search(full_content):
                break

        match = _TEXT_REPLY_FORMAT.search(full_content)
        if not match:
            raise exceptions.InvalidResponse(full_content)

        message = match.group('message')
        _verify_checksum(message, match.group('checksum'))

        if match.group('status') != b'OK':
            raise exceptions.InvalidResponse(message or "Command failed")

        # If there is anything in the response that is not ASCII-safe, this is
        # probably in the patient name. The Windows utility does not seem to
        # validate those, so just replace anything non-ASCII with the correct
        # unknown codepoint.
        return message.decode('ascii', 'replace')

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

    def get_patient_name(self):
        # type: () -> Optional[Text]
        patient_name = self._send_text_command(b'$ptname?').rstrip('\r\n')
        if not patient_name:
            return None
        return patient_name

    def set_patient_name(self, name):
        # type: (Text) -> None
        try:
            encoded_name = name.encode('ascii')
        except UnicodeDecodeError:
            raise ValueError('Only ASCII-safe names are tested working')

        result = self._send_text_command(b'$ptname,' + encoded_name)

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

        # At least Precision Neo devices can have an invalid date (bad RTC?),
        # and report 255 for each field, which is not valid for
        # datetime.datetime().
        try:
            return datetime.datetime(year + 2000, month, day, hour, minute)
        except ValueError:
            raise exceptions.InvalidDateTime()

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
        logging.debug('Received multirecord message:\n%s', message)
        if message == "Log Empty\r\n":
            return iter(())

        match = _MULTIRECORDS_FORMAT.search(message)
        if not match:
            raise exceptions.InvalidResponse(message)

        records_str = match.group('message')
        _verify_checksum(records_str, match.group('checksum'))

        logging.debug('Received multi-record string: %s', records_str)

        return csv.reader(records_str.split('\r\n'))
