# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for FreeStyle Optium devices.

Supported features:
    - get readings (ignores ketone results);
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version.

Expected device path: /dev/ttyUSB0 or similar serial port device.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/abbott/freestyle-optium
"""

import datetime
import logging
import re

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import serial


_CLOCK_RE = re.compile(
    r'^Clock:\t(?P<month>[A-Z][a-z]{2})  (?P<day>[0-9]{2}) (?P<year>[0-9]{4})\t'
    r'(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})$')

# The reading can be HI (padded to three-characters by a space) if the value was
# over what the meter was supposed to read. Unlike the "Clock:" line, the months
# of June and July are written in full, everything else is truncated to three
# characters, so accept a space or 'e'/'y' at the end of the month name. Also,
# the time does *not* include seconds.
_READING_RE = re.compile(
    r'^(?P<reading>HI |[0-9]{3})  '
    r'(?P<month>[A-Z][a-z]{2})[ ey] '
    r'(?P<day>[0-9]{2}) '
    r'(?P<year>[0-9]{4}) '
    r'(?P<time>[0-9]{2}:[0-9]{2}) '
    r'(?P<type>[GK]) 0x00$')

_CHECKSUM_RE = re.compile(
    r'^(?P<checksum>0x[0-9A-F]{4})  END$')

# There are two date format used by the device. One uses three-letters month
# names, and that's easy enough. The other uses three-letters month names,
# except for (at least) July. So ignore the fourth character.
# explicit mapping. Note that the mapping *requires* a trailing whitespace.
_MONTH_MATCHES = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12
}


def _parse_clock(datestr):
    """Convert the date/time string used by the the device into a datetime.

    Args:
      datestr: a string as returned by the device during information handling.
    """
    match = _CLOCK_RE.match(datestr)
    if not match:
        raise exceptions.InvalidResponse(datestr)

    # int() parses numbers in decimal, so we don't have to worry about '08'
    day = int(match.group('day'))
    month = _MONTH_MATCHES[match.group('month')]
    year = int(match.group('year'))

    hour, minute, second = (int (x) for x in match.group('time').split(':'))

    return datetime.datetime(year, month, day, hour, minute, second)


class Device(serial.SerialDevice):
    BAUDRATE = 19200
    DEFAULT_CABLE_ID = '1a61:3420'

    def _send_command(self, command):
        cmd_bytes = bytes('$%s\r\n' % command, 'ascii')
        logging.debug('Sending command: %r', cmd_bytes)

        self.serial_.write(cmd_bytes)
        self.serial_.flush()

        response = self.serial_.readlines()

        logging.debug('Received response: %r', response)

        # We always want to decode the output, and remove stray \r\n. Any
        # failure in decoding means the output is invalid anyway.
        decoded_response = [line.decode('ascii').rstrip('\r\n')
                            for line in response]
        return decoded_response

    def connect(self):
        self._send_command('xmem') # ignore output this time
        self._fetch_device_information()

    def disconnect(self):  # pylint: disable=no-self-use
        return

    def _fetch_device_information(self):
        data = self._send_command('colq')

        for line in data:
            parsed_line = line.split('\t')

            if parsed_line[0] == 'S/N:':
                self.device_serialno_ = parsed_line[1]
            elif parsed_line[0] == 'Ver:':
                self.device_version_ = parsed_line[1]
                if parsed_line[2] == 'MMOL':
                    self.device_glucose_unit_ = common.Unit.MMOL_L
                else:  # I only have a mmol/l device, so I can't be sure.
                    self.device_glucose_unit_ = common.Unit.MG_DL
            # There are more entries: Clock, Market, ROM and Usage, but we don't
            # care for those here.
            elif parsed_line[0] == 'CMD OK':
                return

        # I have not figured out why this happens, but sometimes it's echoing
        # back the commands and not replying to them.
        raise exceptions.ConnectionFailed()

    def get_meter_info(self):
        """Fetch and parses the device information.

        Returns:
          A common.MeterInfo object.
        """
        return common.MeterInfo(
            'Freestyle Optium glucometer',
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self.get_version(),),
            native_unit=self.get_glucose_unit())

    def get_version(self):
        """Returns an identifier of the firmware version of the glucometer.

        Returns:
          The software version returned by the glucometer, such as "0.22"
        """
        return self.device_version_

    def get_serial_number(self):
        """Retrieve the serial number of the device.

        Returns:
          A string representing the serial number of the device.
        """
        return self.device_serialno_

    def get_glucose_unit(self):
        """Returns a constant representing the unit displayed by the meter.

        Returns:
          common.Unit.MG_DL: if the glucometer displays in mg/dL
          common.Unit.MMOL_L: if the glucometer displays in mmol/L
        """
        return self.device_glucose_unit_

    def get_datetime(self):
        """Returns the current date and time for the glucometer.

        Returns:
          A datetime object built according to the returned response.
        """
        data = self._send_command('colq')

        for line in data:
            if not line.startswith('Clock:'):
                continue

            return _parse_clock(line)

        raise exceptions.InvalidResponse('\n'.join(data))

    def set_datetime(self, date=datetime.datetime.now()):
        """Sets the date and time of the glucometer.

        Args:
          date: The value to set the date/time of the glucometer to. If none is
            given, the current date and time of the computer is used.

        Returns:
          A datetime object built according to the returned response.
        """
        data = self._send_command(date.strftime('tim,%m,%d,%y,%H,%M'))

        parsed_data = ''.join(data)
        if parsed_data != 'CMD OK':
            raise exceptions.InvalidResponse(parsed_data)

        return self.get_datetime()

    def zero_log(self):
        raise NotImplementedError

    def get_readings(self):
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
        data = self._send_command('xmem')

        # The first line is empty, the second is the serial number, the third
        # the version, the fourth the current time, and the fifth the record
        # count.. The last line has a checksum and the end.
        count = int(data[4])
        if count != (len(data) - 6):
            raise exceptions.InvalidResponse('\n'.join(data))

        # Extract the checksum from the last line.
        checksum_match = _CHECKSUM_RE.match(data[-1])
        if not checksum_match:
            raise exceptions.InvalidResponse('\n'.join(data))

        expected_checksum = int(checksum_match.group('checksum'), 16)
        # exclude the last line in the checksum calculation, as that's the
        # checksum itself. The final \r\n is added separately.
        calculated_checksum = sum(
            ord(c) for c in '\r\n'.join(data[:-1])) + 0xd + 0xa

        if expected_checksum != calculated_checksum:
            raise exceptions.InvalidChecksum(
                expected_checksum, calculated_checksum)

        for line in data[5:-1]:
            match = _READING_RE.match(line)
            if not match:
                raise exceptions.InvalidResponse(line)

            if match.group('type') != 'G':
                logging.warning(
                    'Non-glucose readings are not supported, ignoring.')
                continue

            if match.group('reading') == 'HI ':
                value = float("inf")
            else:
                value = float(match.group('reading'))

            day = int(match.group('day'))
            month = _MONTH_MATCHES[match.group('month')]
            year = int(match.group('year'))

            hour, minute = map(int, match.group('time').split(':'))

            timestamp = datetime.datetime(year, month, day, hour, minute)

            # The reading, if present, is always in mg/dL even if the glucometer
            # is set to mmol/L.
            yield common.GlucoseReading(timestamp, value)
