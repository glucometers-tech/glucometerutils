# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for ContourUSB devices.

Supported features:
    - get readings (blood glucose), including comments;
    - get date and time;
    - get serial number and software version;
    - get device info (e.g. unit)

Expected device path: /dev/hidraw4 or similar HID device. Optional when using
HIDAPI.

Further information on the device protocol can be found at

http://protocols.ascensia.com/Programming-Guide.aspx

"""

import datetime

from glucometerutils import common
from glucometerutils.support import contourusb

def _extract_timestamp(parsed_record, prefix=''):
    """Extract the timestamp from a parsed record.

    This leverages the fact that all the reading records have the same base structure.
    """
    datetime_str = parsed_record['datetime']

    return datetime.datetime(
        int(datetime_str[0:4]), #year
        int(datetime_str[4:6]), #month
        int(datetime_str[6:8]), #day
        int(datetime_str[8:10]), #hour
        int(datetime_str[10:12]), #minute
        0)


class Device(contourusb.ContourHidDevice):
    """Glucometer driver for FreeStyle Libre devices."""

    USB_VENDOR_ID = 0x1a79  # type: int  # Bayer Health Care LLC Contour
    USB_PRODUCT_ID = 0x6002  # type: int


    def get_meter_info(self):
        """Return the device information in structured form."""
        self._get_info_record()
        return common.MeterInfo(
            'Contour USB',
            serial_number=self._get_serial_number(),
            version_info=(
                'Meter versions: ' + self._get_version(),),
            native_unit= self.get_glucose_unit())

    def get_glucose_unit(self):  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""
        
        if self._get_glucose_unit() == '0':
            return common.Unit.MG_DL
        else:
            return common.Unit.MMOL_L
        

    def get_readings(self):
        """
        Get reading dump from download data mode(all readings stored)
        This meter supports only blood samples
        """
        for parsed_record in self._get_multirecord():
            yield common.GlucoseReading(
                _extract_timestamp(parsed_record),
                int(parsed_record['value']),
                comment=parsed_record['markers'],
                measure_method=common.MeasurementMethod.BLOOD_SAMPLE
                )
            

