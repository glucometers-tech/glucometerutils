# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2020 The glucometerutils Authors
# SPDX-License-Identifier: MIT

import abc
import dataclasses
import datetime
import importlib
import inspect
from collections.abc import Generator
from typing import Optional

from glucometerutils import common


class GlucometerDevice(abc.ABC):
    def __init__(self, device_path: Optional[str]) -> None:
        pass

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    @abc.abstractmethod
    def get_meter_info(self) -> common.MeterInfo:
        """Return the device information in structured form."""
        pass

    @abc.abstractmethod
    def get_serial_number(self) -> str:
        pass

    @abc.abstractmethod
    def get_glucose_unit(self) -> common.Unit:
        """Returns the glucose unit of the device."""
        pass

    @abc.abstractmethod
    def get_datetime(self) -> datetime.datetime:
        pass

    def set_datetime(
        self, date: Optional[datetime.datetime] = None
    ) -> datetime.datetime:
        """Sets the date and time of the glucometer.

        Args:
          date: The value to set the date/time of the glucometer to. If none is
            given, the current date and time of the computer is used.

        Returns:
          A datetime object built according to the returned response.
        """
        if not date:
            date = datetime.datetime.now()
        return self._set_device_datetime(date)

    @abc.abstractmethod
    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        pass

    @abc.abstractmethod
    def zero_log(self) -> None:
        pass

    @abc.abstractmethod
    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        pass


@dataclasses.dataclass
class Driver:
    device: type[GlucometerDevice]
    help: str


def load_driver(driver_name: str) -> Driver:
    driver_module = importlib.import_module(f"glucometerutils.drivers.{driver_name}")
    help_string = inspect.getdoc(driver_module)
    assert help_string is not None

    return Driver(getattr(driver_module, "Device"), help_string)
