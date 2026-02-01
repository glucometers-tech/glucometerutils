# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2026 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for Accu-Chek Guide and compatible USB devices.

Supported features:
    - get readings (blood glucose);
    - get basic device info (model, serial if available).

Expected device path: optional; if provided, use vid:pid (hex or decimal).
"""

import datetime
from collections.abc import Generator
from typing import NoReturn, Optional

from glucometerutils import common, driver
from glucometerutils.support import accuchek_guide


class Device(driver.GlucometerDevice):
    def __init__(self, device: Optional[str]) -> None:
        self._session = accuchek_guide.AccuChekGuideSession(device)

    def connect(self) -> None:
        self._session.open()

    def disconnect(self) -> None:
        self._session.close()

    def get_meter_info(self) -> common.MeterInfo:
        return common.MeterInfo(
            self._session.get_model_name(),
            serial_number=self._session.get_serial_number(),
            native_unit=self.get_glucose_unit(),
        )

    def get_serial_number(self) -> str:
        return self._session.get_serial_number()

    def get_glucose_unit(self) -> common.Unit:
        return common.Unit.MG_DL

    def get_datetime(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def _set_device_datetime(self, date: datetime.datetime) -> NoReturn:
        raise NotImplementedError

    def zero_log(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        yield from self._session.download_readings()
