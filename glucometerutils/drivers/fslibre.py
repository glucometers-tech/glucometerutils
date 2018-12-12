# -*- coding: utf-8 -*-
"""Driver for FreeStyle Libre devices.

Supported features:
    - get readings (sensor, flash and blood glucose), including comments;
    - get and set date and time;
    - get serial number and software version.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

Further information on the device protocol can be found at

https://flameeyes.github.io/glucometer-protocols/abbott/freestyle-libre

"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2017, Diego Elio Pettenò'
__license__ = 'MIT'

import datetime

from glucometerutils import common
from glucometerutils.support import freestyle

# Fields of the records returned by both $history and $arresult?
# Tuple of pairs of idx and field name
_BASE_ENTRY_MAP = (
    (1, 'type'),
    (2, 'month'),
    (3, 'day'),
    (4, 'year'),  # 2-digits
    (5, 'hour'),
    (6, 'minute'),
    (7, 'second'),
)

# Fields of the records returned by $history?
_HISTORY_ENTRY_MAP = _BASE_ENTRY_MAP + (
    (13, 'value'),
    (15, 'errors'),
)

# Fields of the results returned by $arresult? where type = 2
_ARRESULT_TYPE2_ENTRY_MAP = (
    (9, 'reading-type'),  # 0 = glucose blood strip,
                          # 1 = ketone blood strip,
                          # 2 = glucose sensor
    (12, 'value'),
    (15, 'sport-flag'),
    (16, 'medication-flag'),
    (17, 'rapid-acting-flag'),  # see _ARRESULT_RAPID_INSULIN_ENTRY_MAP
    (18, 'long-acting-flag'),
    (19, 'custom-comments-bitfield'),
    (23, 'double-long-acting-insulin'),
    (25, 'food-flag'),
    (26, 'food-carbs-grams'),
    (28, 'errors'),
)

# Fields only valid when rapid-acting-flag is "1"
_ARRESULT_RAPID_INSULIN_ENTRY_MAP = (
    (43, 'double-rapid-acting-insulin'),
)


def _parse_record(record, entry_map):
    """Parses a list of string fields into a dictionary of integers."""

    if not record:
        return {}

    try:
        return {
            key: int(record[idx]) for idx, key in entry_map
        }
    except IndexError:
        return {}


def _extract_timestamp(parsed_record):
    """Extract the timestamp from a parsed record.

    This leverages the fact that all the records have the same base structure.
    """

    return datetime.datetime(
        parsed_record['year'] + 2000,
        parsed_record['month'],
        parsed_record['day'],
        parsed_record['hour'],
        parsed_record['minute'],
        parsed_record['second'])


def _convert_ketone_unit(raw_value):
    """Convert raw ketone value as read in the device to its value in mmol/L."""
    return int((raw_value + 1) / 2.) / 10.


def _parse_arresult(record):
    """Takes an array of string fields as input and parses it into a Reading."""

    parsed_record = _parse_record(record, _BASE_ENTRY_MAP)

    # There are other record types, but we don't currently need to expose these.
    if not parsed_record or parsed_record['type'] != 2:
        return None

    parsed_record.update(_parse_record(record, _ARRESULT_TYPE2_ENTRY_MAP))

    # Check right away if we have rapid insulin
    if parsed_record['rapid-acting-flag']:
        parsed_record.update(
            _parse_record(record, _ARRESULT_RAPID_INSULIN_ENTRY_MAP))

    if parsed_record['errors']:
        return None

    comment_parts = []
    measure_method = None
    cls = None
    value = None

    if parsed_record['reading-type'] == 2:
        comment_parts.append('(Scan)')
        measure_method = common.MeasurementMethod.CGM
        cls = common.GlucoseReading
        value = parsed_record['value']
    elif parsed_record['reading-type'] == 0:
        comment_parts.append('(Blood)')
        measure_method = common.MeasurementMethod.BLOOD_SAMPLE
        cls = common.GlucoseReading
        value = parsed_record['value']
    elif parsed_record['reading-type'] == 1:
        comment_parts.append('(Ketone)')
        measure_method = common.MeasurementMethod.BLOOD_SAMPLE
        cls = common.KetoneReading
        # automatically convert the raw value in mmol/L
        value = _convert_ketone_unit(parsed_record['value'])
    else:
        # unknown reading
        return None

    custom_comments = record[29:35]
    for comment_index in range(6):
        if parsed_record['custom-comments-bitfield'] & (1 << comment_index):
            comment_parts.append(custom_comments[comment_index][1:-1])

    if parsed_record['sport-flag']:
        comment_parts.append('Sport')

    if parsed_record['medication-flag']:
        comment_parts.append('Medication')

    if parsed_record['food-flag']:
        if parsed_record['food-carbs-grams']:
            comment_parts.append(
                'Food (%d g)' % parsed_record['food-carbs-grams'])
        else:
            comment_parts.append('Food')

    if parsed_record['long-acting-flag']:
        if parsed_record['double-long-acting-insulin']:
            comment_parts.append(
                'Long-acting insulin (%.1f)' %
                (parsed_record['double-long-acting-insulin']/2.))
        else:
            comment_parts.append('Long-acting insulin')

    if parsed_record['rapid-acting-flag']:
        # provide default value, as this record does not always exist
        # (even if rapid-acting-flag is set)
        if parsed_record.get('double-rapid-acting-insulin', 0):
            comment_parts.append(
                'Rapid-acting insulin (%.1f)' %
                (parsed_record['double-rapid-acting-insulin']/2.))
        else:
            comment_parts.append('Rapid-acting insulin')


    return cls(
        _extract_timestamp(parsed_record),
        value,
        comment='; '.join(comment_parts),
        measure_method=measure_method)

class Device(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle Libre devices."""

    USB_PRODUCT_ID = 0x3650

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

    def get_glucose_unit(self):  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""
        # TODO(Flameeyes): figure out how to identify the actual unit on the
        # device.
        return common.Unit.MG_DL

    def get_readings(self):

        # First of all get the usually longer list of sensor readings, and
        # convert them to Readings objects.
        for record in self._get_multirecord(b'$history?'):
            parsed_record = _parse_record(record, _HISTORY_ENTRY_MAP)

            if not parsed_record or parsed_record['errors'] != 0:
                # The reading is considered invalid, so ignore it.
                continue

            yield common.GlucoseReading(
                _extract_timestamp(parsed_record),
                parsed_record['value'],
                comment='(Sensor)',
                measure_method=common.MeasurementMethod.CGM)

        # Then get the results of explicit scans and blood tests (and other
        # events).
        for record in self._get_multirecord(b'$arresult?'):
            reading = _parse_arresult(record)
            if reading:
                yield reading
