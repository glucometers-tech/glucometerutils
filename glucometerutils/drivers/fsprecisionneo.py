# -*- coding: utf-8 -*-
"""Driver for FreeStyle Precision Neo devices.

This driver may also work with FreeStyle Optium Neo devices, but it is currently
untested.

Supported features:
    - get readings;
    - get and set date and time;
    - get serial number and software version.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

Further information on the device protocol can be found at

https://flameeyes.github.io/glucometer-protocols/abbott/freestyle-precision-neo

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
_TYPE_GLUCOSE_READING = '7'
_TYPE_KETONE_READING = '9'

_NeoReading = collections.namedtuple('_NeoReading', (
    'type',  # 7 = blood glucose, 9 = blood ketone
    'id',
    'month', 'day', 'year',  # year is two-digits
    'hour', 'minute',
    'unknown2',
    'value',
    # Extra trailing and so-far-unused fields; so discard them:
    # * for blood glucose: 10 unknown trailing fields
    #'unknown3', 'unknown4', 'unknown5', 'unknown6', 'unknown7',
    #'unknown8', 'unknown9', 'unknown10', 'unknown11', 'unknown12',
    # * for blood ketone: 2 unknown trailing fields
    #'unknown3', 'unknown4',
))


class Device(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle Precision Neo devices."""

    USB_PRODUCT_ID = 0x3850

    def get_meter_info(self):
        """Return the device information in structured form."""
        return common.MeterInfo(
            'FreeStyle Precision Neo',
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
            cls = None
            if record and record[0] == _TYPE_GLUCOSE_READING:
                cls = common.GlucoseReading
            elif record and record[0] == _TYPE_KETONE_READING:
                cls = common.KetoneReading
            else:
                continue

            # Build a _reading object by parsing each of the entries in the raw
            # record
            values = [int(v) for v in record]
            raw_reading = _NeoReading._make(values[:len(_NeoReading._fields)])

            timestamp = datetime.datetime(
                raw_reading.year + 2000, raw_reading.month, raw_reading.day,
                raw_reading.hour, raw_reading.minute)

            yield cls(timestamp, raw_reading.value)
