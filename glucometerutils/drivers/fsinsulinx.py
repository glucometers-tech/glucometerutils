# -*- coding: utf-8 -*-
"""Driver for FreeStyle InsuLinx devices.

Supported features:
    - get readings;
    - get and set date and time;
    - get serial number and software version.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

WARNING: currently untested! Based off reverse engineering notes provided by
Xavier Claessens.

"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2017, Diego Elio Pettenò'
__license__ = 'MIT'

import collections
import datetime

from glucometerutils import common
from glucometerutils.support import freestyle


# The type is a string because it precedes the parsing of the object.
_TYPE_GLUCOSE_READING = '0'

_InsulinxReading = collections.namedtuple('_InsulinxReading', (
    'type',  # 0 = blood glucose
    'id',
    'month', 'day', 'year',  # year is two-digits
    'hour', 'minute',
    'unknown1', 'unknown2', 'unknown3',
    'unknown4', 'unknown5', 'unknown6',
    'value',
    'unknown7', 'unknown8',
))


class Device(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle InsuLinux devices."""

    USB_PRODUCT_ID = 0x3460

    def get_meter_info(self):
        """Return the device information in structured form."""
        return common.MeterInfo(
            'FreeStyle InsuLinx',
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self._get_version(),),
            native_unit=self.get_glucose_unit())

    def get_glucose_unit(self):
        """Returns the glucose unit of the device."""
        return common.UNIT_MGDL

    def get_readings(self):
        """Iterate through the reading records in the device."""
        for record in self._get_multirecord(b'$result?'):
            if not record or record[0] != _TYPE_GLUCOSE_READING:
                continue

            # Build a reading object by parsing each of the entries in the CSV
            # as integers.
            raw_reading = _InsulinxReading._make([int(v) for v in record])

            timestamp = datetime.datetime(
                raw_reading.year + 2000, raw_reading.month, raw_reading.day,
                raw_reading.hour, raw_reading.minute)

            yield common.GlucoseReading(timestamp, raw_reading.value)
