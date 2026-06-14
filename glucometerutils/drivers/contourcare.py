# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2019 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for Contour Care devices.

Supported features:
    - get readings (blood glucose), including comments;
    - get date and time;
    - get serial number and software version;
    - get device info (e.g. unit)

Expected device path: /dev/hidraw4 or similar HID device. Optional when using
HIDAPI.
"""

import datetime
from collections.abc import Generator
from typing import NoReturn, Optional

from glucometerutils import common
from glucometerutils.support import contourcare

_MEAL_CODES = {
    "T": common.Meal.NONE,
    "B": common.Meal.BEFORE,
    "A": common.Meal.AFTER,
    "F": common.Meal.FASTING,
}

_UNIT_CODES = {
    "mg/dL": common.Unit.MG_DL,
    "mmol/L": common.Unit.MMOL_L,
}

PRODUCT_ID: int = 0x7950  # Contour Care


class Device(contourcare.ContourCareHidDevice):
    """Glucometer driver for Contour Care devices."""

    def __init__(self, device: Optional[str]) -> None:
        super().__init__(PRODUCT_ID, device)

    def get_meter_info(self) -> common.MeterInfo:
        self._get_info_record()
        return common.MeterInfo(
            "Contour Care",
            serial_number=self.get_serial_number(),
            version_info=("Meter versions: " + self.get_version(),),
            native_unit=self.get_glucose_unit(),
        )

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        """
        Get reading dump from download data mode(all readings stored)
        This meter supports only blood samples
        """
        for parsed_record in self._get_multirecord():
            timestamp = self.parse_timestamp(parsed_record["datetime"])
            value = float(parsed_record["value"])
            yield common.GlucoseReading(
                timestamp,
                value,
                _MEAL_CODES[parsed_record["meal"][0]],
                measure_method=common.MeasurementMethod.BLOOD_SAMPLE,
                unit=_UNIT_CODES[parsed_record["unit"]],
            )

    def get_serial_number(self) -> str:
        return self._get_serial_number()

    def get_version(self):
        return self._get_version()

    def get_glucose_unit(self) -> common.Unit:
        if self._get_glucose_unit() == "0":
            return common.Unit.MG_DL
        else:
            return common.Unit.MMOL_L

    def _set_device_datetime(self, date: datetime.datetime) -> NoReturn:
        raise NotImplementedError

    def zero_log(self) -> NoReturn:
        raise NotImplementedError

    def get_patient_name(self) -> str:
        raise NotImplementedError

    def set_patient_name(self, name: str) -> None:
        raise NotImplementedError
