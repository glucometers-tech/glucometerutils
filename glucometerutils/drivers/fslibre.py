# -*- coding: utf-8 -*-
"""Driver for FreeStyle Libre CGM devices."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2017, Diego Elio Pettenò'
__license__ = 'MIT'

import datetime

from glucometerutils import common
from glucometerutils.support import freestyle

# Fields of the records returned by $history?
# Tuple of pairs of idx and field name
_HISTORY_ENTRY_MAP = (
    (2, 'month'),
    (3, 'day'),
    (4, 'year'),  # 2-digits
    (5, 'hour'),
    (6, 'minute'),
    (7, 'second'),
    (13, 'value'),
    (15, 'errors'),
)


class Device(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle Libre devices."""

    def get_meter_info(self):
        """Return the device information in structured form."""
        return common.MeterInfo(
            'FreeStyle Libre',
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self._get_version(),),
            native_unit=self.get_glucose_unit())

    def get_serial_number(self):
        """Overridden function as the command is not compatible."""
        return self._send_text_command(b'$sn?').rstrip('\r\n')

    def get_glucose_unit(self):
        """Returns the glucose unit of the device."""
        # TODO(Flameeyes): figure out how to identify the actual unit on the
        # device.
        return common.UNIT_MGDL

    def get_readings(self):
        for record in self._get_multirecord(b'$history?'):
            if not record:
                continue

            parsed_record = {
                key: int(record[idx])
                for idx, key in _HISTORY_ENTRY_MAP
            }

            if parsed_record['errors'] != 0:
                # The reading is considered invalid, so ignore it.
                continue

            timestamp = datetime.datetime(
                parsed_record['year'] + 2000,
                parsed_record['month'],
                parsed_record['day'],
                parsed_record['hour'],
                parsed_record['minute'],
                parsed_record['second'])

            yield common.Reading(timestamp, parsed_record['value'],
                                 comment='(Sensor)')
