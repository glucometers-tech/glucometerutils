# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for LifeScan OneTouch Ultra 2 devices.

Supported features:
    - get readings, including pre-/post-meal notes and other comments;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/ttyUSB0 or similar serial port device.
"""

import datetime
import re
from collections.abc import Generator

from glucometerutils import common, driver, exceptions
from glucometerutils.support import lifescan, serial

# The following two hashes are taken directly from LifeScan's documentation
_MEAL_CODES = {
    "N": common.Meal.NONE,
    "B": common.Meal.BEFORE,
    "A": common.Meal.AFTER,
}

_COMMENT_CODES = {
    "00": "",  # would be 'No Comment'
    "01": "Not Enough Food",
    "02": "Too Much Food",
    "03": "Mild Exercise",
    "04": "Hard Exercise",
    "05": "Medication",
    "06": "Stress",
    "07": "Illness",
    "08": "Feel Hypo",
    "09": "Menses",
    "10": "Vacation",
    "11": "Other",
}

_DUMP_HEADER_RE = re.compile(r'P ([0-9]{3}),"[0-9A-Z]{9}","(?:MG/DL |MMOL/L)"')
_DUMP_LINE_RE = re.compile(
    r'P (?P<datetime>"[A-Z]{3}","[0-9/]{8}","[0-9:]{8}   "),'
    r'"(?P<control>[C ]) (?P<value>[0-9]{3})(?P<parityerror>[\? ])",'
    r'"(?P<meal>[NBA])","(?P<comment>0[0-9]|1[01])", 00'
)

_RESPONSE_MATCH = re.compile(r"^(.+) ([0-9A-F]{4})\r$")


def _calculate_checksum(bytestring: bytes) -> int:
    """Calculate the checksum used by OneTouch Ultra and Ultra2 devices

    Args:
      bytestring: the string of which the checksum has to be calculated.

    Returns:
      A string with the hexdecimal representation of the checksum for the input.

    The checksum is a very stupid one: it just sums all the bytes,
    modulo 16-bit, without any parity.
    """
    checksum = 0

    for byte in bytestring:
        checksum = (checksum + byte) & 0xFFFF

    return checksum


def _validate_and_strip_checksum(line: str) -> str:
    """Verify the simple 16-bit checksum and remove it from the line.

    Args:
      line: the line to check the checksum of.

    Returns:
      A copy of the line with the checksum stripped out.
    """
    match = _RESPONSE_MATCH.match(line)

    if not match:
        raise lifescan.MissingChecksum(line)

    response, checksum_string = match.groups()

    try:
        checksum_given = int(checksum_string, 16)
        checksum_calculated = _calculate_checksum(bytes(response, "ascii"))

        if checksum_given != checksum_calculated:
            raise exceptions.InvalidChecksum(checksum_given, checksum_calculated)
    except ValueError:
        raise exceptions.InvalidChecksum(checksum_given, None)

    return response


_DATETIME_RE = re.compile(
    r'^"[A-Z]{3}",' r'"([0-9]{2}/[0-9]{2}/[0-9]{2})","([0-9]{2}:[0-9]{2}:[0-9]{2})   "$'
)


def _parse_datetime(response: str) -> datetime.datetime:
    """Convert a response with date and time from the meter into a datetime.

    Args:
      response: the response coming from a DMF or DMT command

    Returns:
      A datetime object built according to the returned response.

    Raises:
      InvalidResponse if the string cannot be matched by _DATETIME_RE.
    """
    match = _DATETIME_RE.match(response)
    if not match:
        raise exceptions.InvalidResponse(response)

    date, time = match.groups()
    month, day, year = map(int, date.split("/"))
    hour, minute, second = map(int, time.split(":"))

    # Yes, OneTouch2's firmware is not Y2K safe.
    return datetime.datetime(2000 + year, month, day, hour, minute, second)


class Device(serial.SerialDevice, driver.GlucometerDevice):
    BAUDRATE = 9600
    DEFAULT_CABLE_ID = "067b:2303"  # Generic PL2303 cable.

    def connect(self) -> None:  # pylint: disable=no-self-use
        return

    def disconnect(self) -> None:  # pylint: disable=no-self-use
        return

    def _send_command(self, cmd: str) -> None:
        """Send command interface.

        Args:
          cmd: command and parameters to send (without newline)
        """
        cmdstring = bytes(f"\x11\r{cmd}\r", "ascii")
        self.serial_.write(cmdstring)
        self.serial_.flush()

    def _send_oneliner_command(self, cmd: str) -> str:
        """Send command and read a one-line response.

        Args:
          cmd: command and parameters to send (without newline)

        Returns:
          A single line of text that the glucometer responds, without the
          checksum.
        """
        self._send_command(cmd)

        line = self.serial_.readline().decode("ascii")
        return _validate_and_strip_checksum(line)

    def get_meter_info(self) -> common.MeterInfo:
        """Fetch and parses the device information.

        Returns:
          A common.MeterInfo object.
        """
        return common.MeterInfo(
            "OneTouch Ultra 2 glucometer",
            serial_number=self.get_serial_number(),
            version_info=("Software version: " + self.get_version(),),
            native_unit=self.get_glucose_unit(),
        )

    def get_version(self) -> str:
        """Returns an identifier of the firmware version of the glucometer.

        Returns:
          The software version returned by the glucometer, such as
            "P02.00.00 30/08/06".
        """
        response = self._send_oneliner_command("DM?")

        if response[0] != "?":
            raise exceptions.InvalidResponse(response)

        return response[1:]

    _SERIAL_NUMBER_RE = re.compile('^@ "([A-Z0-9]{9})"$')

    def get_serial_number(self) -> str:
        """Retrieve the serial number of the device.

        Returns:
          A string representing the serial number of the device.

        Raises:
          exceptions.InvalidResponse: if the DM@ command returns a string not
            matching _SERIAL_NUMBER_RE.
          InvalidSerialNumber: if the returned serial number does not match
            the OneTouch2 device as per specs.
        """
        response = self._send_oneliner_command("DM@")

        match = self._SERIAL_NUMBER_RE.match(response)
        if not match:
            raise exceptions.InvalidResponse(response)

        serial_number = match.group(1)

        # 'Y' at the far right of the serial number is the indication of a
        # OneTouch Ultra2 device, as per specs.
        if serial_number[-1] != "Y":
            raise lifescan.InvalidSerialNumber(serial_number)

        return serial_number

    def get_datetime(self) -> datetime.datetime:
        """Returns the current date and time for the glucometer.

        Returns:
          A datetime object built according to the returned response.
        """
        response = self._send_oneliner_command("DMF")
        return _parse_datetime(response[2:])

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        response = self._send_oneliner_command(
            "DMT" + date.strftime("%m/%d/%y %H:%M:%S")
        )
        return _parse_datetime(response[2:])

    def zero_log(self) -> None:
        """Zeros out the data log of the device.

        This function will clear the memory of the device deleting all the
        readings in an irrecoverable way.
        """
        response = self._send_oneliner_command("DMZ")
        if response != "Z":
            raise exceptions.InvalidResponse(response)

    _GLUCOSE_UNIT_RE = re.compile(r'^SU\?,"(MG/DL |MMOL/L)"')

    def get_glucose_unit(self) -> common.Unit:
        """Returns a constant representing the unit displayed by the meter.

        Returns:
          common.Unit.MG_DL: if the glucometer displays in mg/dL
          common.Unit.MMOL_L: if the glucometer displays in mmol/L

        Raises:
          exceptions.InvalidGlucoseUnit: if the unit is not recognized

        OneTouch meters will always dump data in mg/dL because that's their
        internal storage. They will then provide a separate method to read the
        unit used for display. This is not settable by the user in all modern
        meters.
        """
        response = self._send_oneliner_command("DMSU?")

        match = self._GLUCOSE_UNIT_RE.match(response)
        if match is None:
            raise exceptions.InvalidGlucoseUnit(response)

        unit = match.group(1)

        if unit == "MG/DL ":
            return common.Unit.MG_DL

        if unit == "MMOL/L":
            return common.Unit.MMOL_L

        raise exceptions.InvalidGlucoseUnit(response)

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        """Iterates over the reading values stored in the glucometer.

        Args:
          unit: The glucose unit to use for the output.

        Yields:
          A GlucoseReading object representing the read value.

        Raises:
          exceptions.InvalidResponse: if the response does not match what
          expected.

        """
        self._send_command("DMP")
        data = self.serial_.readlines()

        header = data.pop(0).decode("ascii")
        match = _DUMP_HEADER_RE.match(header)
        if not match:
            raise exceptions.InvalidResponse(header)

        count = int(match.group(1))
        assert count == len(data)

        for line in data:
            line = _validate_and_strip_checksum(line.decode("ascii"))

            match = _DUMP_LINE_RE.match(line)
            if not match:
                raise exceptions.InvalidResponse(line)

            line_data = match.groupdict()

            date = _parse_datetime(line_data["datetime"])
            meal = _MEAL_CODES[line_data["meal"]]
            comment = _COMMENT_CODES[line_data["comment"]]

            # OneTouch2 always returns the data in mg/dL even if the glucometer
            # is set to mmol/L, so there is no conversion required.
            yield common.GlucoseReading(
                date, float(line_data["value"]), meal=meal, comment=comment
            )
