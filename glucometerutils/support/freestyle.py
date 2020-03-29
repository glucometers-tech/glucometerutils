# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines to implement the FreeStyle common protocol.

Protocol documentation available at
https://protocols.glucometers.tech/abbott/shared-hid-protocol

"""

import csv
import datetime
import logging
import re
from typing import AnyStr, Callable, Iterator, List, Optional, Tuple

import construct

from glucometerutils import driver, exceptions
from glucometerutils.support import hiddevice

_INIT_COMMAND = 0x01
_INIT_RESPONSE = 0x71

_KEEPALIVE_RESPONSE = 0x22
_UNKNOWN_MESSAGE_RESPONSE = 0x30

_ENCRYPTION_SETUP_COMMAND = 0x14
_ENCRYPTION_SETUP_RESPONSE = 0x33

_ALWAYS_UNENCRYPTED_MESSAGES = (
    _INIT_COMMAND,
    0x04,
    0x05,
    0x06,
    0x0C,
    0x0D,
    _ENCRYPTION_SETUP_COMMAND,
    0x15,
    _ENCRYPTION_SETUP_RESPONSE,
    0x34,
    0x35,
    _INIT_RESPONSE,
    _KEEPALIVE_RESPONSE,
)


def _create_matcher(
    message_type: int, content: Optional[bytes]
) -> Callable[[Tuple[int, bytes]], bool]:
    def _matcher(message: Tuple[int, bytes]) -> bool:
        return message[0] == message_type and (content is None or content == message[1])

    return _matcher


_is_init_reply = _create_matcher(_INIT_RESPONSE, b"\x01")
_is_keepalive_response = _create_matcher(_KEEPALIVE_RESPONSE, None)
_is_unknown_message_error = _create_matcher(_UNKNOWN_MESSAGE_RESPONSE, b"\x85")
_is_encryption_missing_error = _create_matcher(_ENCRYPTION_SETUP_RESPONSE, b"\x15")
_is_encryption_setup_error = _create_matcher(_ENCRYPTION_SETUP_RESPONSE, b"\x14")

_FREESTYLE_MESSAGE = construct.Struct(
    "hid_report" / construct.Const(0, construct.Byte),
    "message_type" / construct.Byte,
    "command"
    / construct.Padded(
        63,  # command can only be up to 62 bytes, but one is used for length.
        construct.Prefixed(construct.Byte, construct.GreedyBytes),
    ),
)

_FREESTYLE_ENCRYPTED_MESSAGE = construct.Struct(
    "hid_report" / construct.Const(0, construct.Byte),
    "message_type" / construct.Byte,
    "command"
    / construct.Padded(
        63,  # command can only be up to 62 bytes, but one is used for length.
        construct.GreedyBytes,
    ),
)

_TEXT_COMPLETION_RE = re.compile(b"CMD (?:OK|Fail!)")
_TEXT_REPLY_FORMAT = re.compile(
    b"^(?P<message>.*)CKSM:(?P<checksum>[0-9A-F]{8})\r\n"
    b"CMD (?P<status>OK|Fail!)\r\n$",
    re.DOTALL,
)

_MULTIRECORDS_FORMAT = re.compile(
    "^(?P<message>.+\r\n)(?P<count>[0-9]+),(?P<checksum>[0-9A-F]{8})\r\n$", re.DOTALL
)


def _verify_checksum(message: AnyStr, expected_checksum_hex: AnyStr) -> None:
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


def convert_ketone_unit(raw_value: float) -> float:
    """Convert raw ketone value as read in the device to its value in mmol/L.

    As per https://protocols.glucometers.tech/abbott/freestyle-libre this is
    actually not using any mg/dL→mmol/L conversion, but rather the same as the
    meter uses for blood glucose.

    """
    return raw_value / 18.0


ABBOTT_VENDOR_ID = 0x1A61


class FreeStyleHidSession:
    def __init__(
        self,
        product_id: int,
        device_path: Optional[str],
        text_message_type: int,
        text_reply_message_type: int,
    ) -> None:

        self._hid_session = hiddevice.HidSession(
            (ABBOTT_VENDOR_ID, product_id), device_path
        )
        self._text_message_type = text_message_type
        self._text_reply_message_type = text_reply_message_type

    def connect(self):
        """Open connection to the device, starting the knocking sequence."""
        self.send_command(_INIT_COMMAND, b"")
        response = self.read_response()
        if not _is_init_reply(response):
            raise exceptions.ConnectionFailed(
                f"Connection error: unexpected message %{response[0]:02x}:{response[1].hex()}"
            )

    def send_command(self, message_type: int, command: bytes, encrypted: bool = False):
        """Send a raw command to the device.

        Args:
          message_type: The first byte sent with the report to the device.
          command: The command to send out the device.
        """
        if encrypted:
            assert message_type not in _ALWAYS_UNENCRYPTED_MESSAGES
            meta_construct = _FREESTYLE_ENCRYPTED_MESSAGE
        else:
            meta_construct = _FREESTYLE_MESSAGE

        usb_packet = meta_construct.build(
            {"message_type": message_type, "command": command}
        )

        logging.debug("Sending packet: %r", usb_packet)
        self._hid_session.write(usb_packet)

    def read_response(self, encrypted: bool = False) -> Tuple[int, bytes]:
        """Read the response from the device and extracts it."""
        usb_packet = self._hid_session.read()

        logging.debug("Read packet: %r", usb_packet)

        assert usb_packet
        message_type = usb_packet[0]

        if not encrypted or message_type in _ALWAYS_UNENCRYPTED_MESSAGES:
            message_length = usb_packet[1]
            message_end_idx = 2 + message_length
            message_content = usb_packet[2:message_end_idx]
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
            return self.read_response(encrypted=encrypted)

        if _is_unknown_message_error(message):
            raise exceptions.CommandError("Invalid command")

        if _is_encryption_missing_error(message):
            raise exceptions.CommandError("Device encryption not initialized.")

        if _is_encryption_setup_error(message):
            raise exceptions.CommandError("Device encryption initialization failed.")

        return message

    def send_text_command(self, command: bytes) -> str:
        """Send a command to the device that expects a text reply."""
        self.send_command(self._text_message_type, command)

        # Reply can stretch multiple buffers
        full_content = b""
        while True:
            message_type, content = self.read_response()

            logging.debug(
                "Received message: type %02x content %s", message_type, content.hex()
            )

            if message_type != self._text_reply_message_type:
                raise exceptions.InvalidResponse(
                    f"Message type {message_type:02x}: content does not match expectations: {content!r}"
                )

            full_content += content

            if _TEXT_COMPLETION_RE.search(full_content):
                break

        match = _TEXT_REPLY_FORMAT.search(full_content)
        if not match:
            raise exceptions.InvalidResponse(repr(full_content))

        message = match.group("message")
        _verify_checksum(message, match.group("checksum"))

        if match.group("status") != b"OK":
            raise exceptions.InvalidResponse(repr(message) or "Command failed")

        # If there is anything in the response that is not ASCII-safe, this is
        # probably in the patient name. The Windows utility does not seem to
        # validate those, so just replace anything non-ASCII with the correct
        # unknown codepoint.
        return message.decode("ascii", "replace")

    def query_multirecord(self, command: bytes) -> Iterator[List[str]]:
        """Queries for, and returns, "multirecords" results.

        Multirecords are used for querying events, readings, history and similar
        other data out of a FreeStyle device. These are comma-separated values,
        variable-length.

        The validation includes the general HID framing parsing, as well as
        validation of the record count, and of the embedded records checksum.

        Args:
          command: The text command to send to the device for the query.

        Returns:
          A CSV reader object that returns a record for each line in the
          reply buffer.
        """
        message = self.send_text_command(command)
        logging.debug("Received multirecord message:\n%s", message)
        if message == "Log Empty\r\n":
            return iter(())

        match = _MULTIRECORDS_FORMAT.search(message)
        if not match:
            raise exceptions.InvalidResponse(message)

        records_str = match.group("message")
        _verify_checksum(records_str, match.group("checksum"))

        logging.debug("Received multi-record string: %s", records_str)

        return csv.reader(records_str.split("\r\n"))


class FreeStyleHidDevice(driver.GlucometerDriver):
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
    ) -> None:
        super().__init__(device_path)
        self._session = FreeStyleHidSession(
            product_id, device_path, text_cmd, text_reply_cmd
        )

    def connect(self) -> None:
        """Open connection to the device, starting the knocking sequence."""
        self._session.connect()

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
            encoded_name = name.encode("ascii")
        except UnicodeDecodeError:
            raise ValueError("Only ASCII-safe names are tested working")

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
