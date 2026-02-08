# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2026 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for Contour Next devices.

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
from collections.abc import Generator
from typing import NoReturn, Optional

from glucometerutils import common
from glucometerutils.support import contourusb


def _extract_timestamp(parsed_record: dict[str, str]):
    """Extract the timestamp from a parsed record.

    This leverages the fact that all the reading records have the same base structure.
    """
    # Pad with zeros for missing time components
    datetime_str = parsed_record["datetime"].ljust(14, '0')
    return datetime.datetime.strptime(datetime_str, '%Y%m%d%H%M%S')


class Device(contourusb.ContourHidDevice):
    """Glucometer driver for Contour Next devices."""

    def __init__(self, device: Optional[str]) -> None:
        super().__init__(
            (0x1A79, 0x7900),
            device,
            header_record_re=contourusb._HEADER_RECORD_RE_NEXT,
        )

    def get_meter_info(self) -> common.MeterInfo:
        self._get_info_record()
        return common.MeterInfo(
            "Contour Next",
            serial_number=self._get_serial_number(),
            version_info=("Meter versions: " + self._get_version(),),
            native_unit=self.get_glucose_unit(),
        )

    def get_glucose_unit(self) -> common.Unit:
        if self._get_glucose_unit() == "0":
            return common.Unit.MG_DL
        else:
            return common.Unit.MMOL_L

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        """
        Get reading dump from download data mode(all readings stored)
        This meter supports only blood samples
        """
        for parsed_record in self._get_multirecord():
            yield common.GlucoseReading(
                _extract_timestamp(parsed_record),
                int(parsed_record["value"]),
                comment=parsed_record["markers"],
                measure_method=common.MeasurementMethod.BLOOD_SAMPLE,
            )

    def get_serial_number(self) -> NoReturn:
        raise NotImplementedError

    def _set_device_datetime(self, date: datetime.datetime) -> NoReturn:
        raise NotImplementedError

    def zero_log(self) -> NoReturn:
        raise NotImplementedError
