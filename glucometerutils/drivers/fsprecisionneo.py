# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for FreeStyle Precision Neo devices.

This driver may also work with FreeStyle Optium Neo devices, but it is currently
untested.

Supported features:
    - get readings;
    - get and set date and time;
    - get serial number and software version;
    - get and set patient name.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/abbott/freestyle-precision-neo

"""

import dataclasses
import datetime
from collections.abc import Generator, Sequence
from typing import NoReturn, Optional

from glucometerutils import common
from glucometerutils.support import freestyle

# The type is a string because it precedes the parsing of the object.
_TYPE_GLUCOSE_READING = "7"
_TYPE_KETONE_READING = "9"


@dataclasses.dataclass
class _NeoReading:
    type: int  # 7 = blood glucose, 9 = blood ketone
    id: int
    month: int
    day: int
    year: int  # year is two-digits
    hour: int
    minute: int
    unknown: int
    value: float
    # Extra trailing and so-far-unused fields; so discard them:
    # * for blood glucose: 10 unknown trailing fields
    # 'unknown3', 'unknown4', 'unknown5', 'unknown6', 'unknown7',
    # 'unknown8', 'unknown9', 'unknown10', 'unknown11', 'unknown12',
    # * for blood ketone: 2 unknown trailing fields
    # 'unknown3', 'unknown4',

    def __init__(self, record: Sequence[str]) -> None:
        for idx, field in enumerate(dataclasses.fields(self)):
            if record[idx] == "HI":
                setattr(self, field.name, float("inf"))
            elif record[idx] == "LO":
                setattr(self, field.name, -float("inf"))
            else:
                setattr(self, field.name, int(record[idx]))


class Device(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle Precision Neo devices."""

    def __init__(self, device_path: Optional[str]):
        super().__init__(0x3850, device_path)

    def get_meter_info(self) -> common.MeterInfo:
        """Return the device information in structured form."""
        return common.MeterInfo(
            "FreeStyle Precision Neo",
            serial_number=self.get_serial_number(),
            version_info=("Software version: " + self._get_version(),),
            native_unit=self.get_glucose_unit(),
            patient_name=self.get_patient_name(),
        )

    def get_glucose_unit(self) -> common.Unit:  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""
        return common.Unit.MG_DL

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        """Iterate through the reading records in the device."""
        for record in self._session.query_multirecord(b"$result?"):
            cls: Optional[type[common.AnyReading]] = None
            if record and record[0] == _TYPE_GLUCOSE_READING:
                cls = common.GlucoseReading
            elif record and record[0] == _TYPE_KETONE_READING:
                cls = common.KetoneReading
            else:
                continue

            # Build a _NeoReading object by parsing each of the entries in the raw
            # record
            raw_reading = _NeoReading(record)

            timestamp = datetime.datetime(
                raw_reading.year + 2000,
                raw_reading.month,
                raw_reading.day,
                raw_reading.hour,
                raw_reading.minute,
            )

            if record and record[0] == _TYPE_KETONE_READING:
                value = freestyle.convert_ketone_unit(raw_reading.value)
            else:
                value = raw_reading.value

            yield cls(timestamp, value)

    def zero_log(self) -> NoReturn:
        raise NotImplementedError
