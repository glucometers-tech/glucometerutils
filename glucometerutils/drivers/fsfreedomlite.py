# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2021 Stefanie Tellex
# SPDX-License-Identifier: MIT
"""Driver for FreeStyle Freedom Lite devices.

Supported features:
    - get readings
    - assumes the device uses mg/dL for the glucose unit
    - get date and time;
    - get serial number and software version.

Expected device path: /dev/ttyUSB0 or similar serial port device.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/abbott/freestyle-lite.html
"""

import datetime
import logging
import re
from typing import Generator, NoReturn, Sequence

from glucometerutils import common, driver, exceptions
from glucometerutils.support import serial

_CLOCK_INIT_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})  (?P<day>[0-9]{2}) (?P<year>[0-9]{4}) "
    r"(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})$"
)

_CLOCK_READING_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})  (?P<day>[0-9]{2}) (?P<year>[0-9]{4}) "
    r"(?P<time>[0-9]{2}:[0-9]{2})$"
)

# The reading can be HI (padded to three-characters by a space) if the value was
# over what the meter was supposed to read. Unlike the "Clock:" line, the months
# of June and July are written in full, everything else is truncated to three
# characters, so accept a space or 'e'/'y' at the end of the month name. Also,
# the time does *not* include seconds.
_READING_RE = re.compile(
    r"^(?P<reading>HI |[0-9]{3})  "
    r"(?P<month>[A-Z][a-z]{2})[ ey] "
    r"(?P<day>[0-9]{2}) "
    r"(?P<year>[0-9]{4}) "
    r"(?P<time>[0-9]{2}:[0-9]{2}) "
    r"(?P<type>[GK]) 0x00$"
)

_CHECKSUM_RE = re.compile(r"^(?P<checksum>0x[0-9A-F]{4})  END$")

# There are two date format used by the device. One uses three-letters month
# names, and that's easy enough. The other uses three-letters month names,
# except for (at least) July. So ignore the fourth character.
# explicit mapping. Note that the mapping *requires* a trailing whitespace.
_MONTH_MATCHES = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _parse_clock_init(datestr: str) -> datetime.datetime:
    """Convert the date/time string used by the device when it sends the current time into a datetime.  This one has seconds.

    Args:
      datestr: a string as returned by the device during initialization.
    """
    match = _CLOCK_INIT_RE.match(datestr)
    if not match:
        raise exceptions.InvalidResponse(datestr)

    # int() parses numbers in decimal, so we don't have to worry about '08'
    day = int(match.group("day"))
    month = _MONTH_MATCHES[match.group("month")]
    year = int(match.group("year"))

    hour, minute, second = (int(x) for x in match.group("time").split(":"))

    return datetime.datetime(year, month, day, hour, minute, second)


def _parse_clock_reading(datestr: str) -> datetime.datetime:
    """Convert the date/time string used by the device into a datetime.

    Args:
      datestr: a string as returned by the device during glucose readings into a datetime.  This one does not have seconds.
    """
    match = _CLOCK_READING_RE.match(datestr)
    if not match:
        raise exceptions.InvalidResponse(datestr)

    # int() parses numbers in decimal, so we don't have to worry about '08'
    day = int(match.group("day"))
    month = _MONTH_MATCHES[match.group("month")]
    year = int(match.group("year"))

    hour, minute = (int(x) for x in match.group("time").split(":"))
    second = 0

    return datetime.datetime(year, month, day, hour, minute, second)


class Device(serial.SerialDevice, driver.GlucometerDevice):
    BAUDRATE = 19200
    DEFAULT_CABLE_ID = "0403:6001"

    def _send_command(self, command: str) -> Sequence[str]:
        cmd_bytes = bytes("$%s\r\n" % command, "ascii")
        logging.debug("Sending command: %r", cmd_bytes)

        self.serial_.write(cmd_bytes)
        self.serial_.flush()

        response = self.serial_.readlines()

        logging.debug("Received response: %r", response)

        # We always want to decode the output, and remove stray \r\n. Any
        # failure in decoding means the output is invalid anyway.
        decoded_response = [line.decode("ascii").rstrip("\r\n") for line in response]
        return decoded_response

    def connect(self) -> None:
        self._fetch_device_information()

    def disconnect(self) -> None:  # pylint: disable=no-self-use
        return

    def _fetch_device_information(self) -> None:
        data = self._send_command("mem")

        self.device_serialno_ = data[1]
        self.device_version_ = data[2]
        self.device_datetime_ = _parse_clock_init(data[3])

        numlines = int(data[4])
        last_line = 6 + numlines

        self._readings = []
        for line in data[6:last_line]:
            glucose = int(line[0:3])
            timestamp = _parse_clock_reading(line[5:23])
            self._readings.append(common.GlucoseReading(timestamp, glucose))

    def get_meter_info(self) -> common.MeterInfo:
        """Fetch and parses the device information.

        Returns:
          A common.MeterInfo object.
        """
        return common.MeterInfo(
            "Freestyle Freedom Lite",
            serial_number=self.get_serial_number(),
            version_info=("Software version: " + self.get_version(),),
            native_unit=self.get_glucose_unit(),
        )

    def get_version(self) -> str:
        """Returns an identifier of the firmware version of the glucometer.

        Returns:
          The software version returned by the glucometer, such as "0.22"
        """
        return self.device_version_

    def get_serial_number(self) -> str:
        """Retrieve the serial number of the device.

        Returns:
          A string representing the serial number of the device.
        """
        return self.device_serialno_

    def get_glucose_unit(self) -> common.Unit:
        """Returns a constant representing the unit displayed by the meter.

        Returns:
          common.Unit.MG_DL: if the glucometer displays in mg/dL
          common.Unit.MMOL_L: if the glucometer displays in mmol/L
        """
        return common.Unit.MG_DL

    def get_datetime(self) -> datetime.datetime:
        """Returns the current date and time for the glucometer.

        Returns:
          A datetime object built according to the returned response.
        """
        return self.device_datetime_

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        raise NotImplementedError

    def zero_log(self) -> NoReturn:
        raise NotImplementedError

    def get_patient_name(self):
        raise NotImplementedError

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        """Iterates over the reading values stored in the glucometer.

        Args:
          unit: The glucose unit to use for the output.

        Yields: A tuple (date, value) of the readings in the glucometer. The
          value is a floating point in the unit specified; if no unit is
          specified, the default unit in the glucometer will be used.

        Raises:
          exceptions.InvalidResponse: if the response does not match what '
          expected.

        """
        for r in self._readings:
            yield r
