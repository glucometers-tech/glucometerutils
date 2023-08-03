# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2016 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for Accu-Chek Mobile devices with reports mode.

Supported features:
    - get readings, including comments;
    - use the glucose unit preset on the device by default;
    - get serial number.

Expected device path: /mnt/ACCUCHEK, the mountpoint of the block device.

The Accu-Chek Mobile meters should be set to "Reports" mode.

"""

import csv
import datetime
import glob
import os
from collections.abc import Generator
from typing import NoReturn, Optional

from glucometerutils import common, driver, exceptions

_UNIT_MAP = {
    "mmol/l": common.Unit.MMOL_L,
    "mg/dl": common.Unit.MG_DL,
}

_DATE_CSV_KEY = "Date"
_TIME_CSV_KEY = "Time"
_RESULT_CSV_KEY = "Result"
_UNIT_CSV_KEY = "Unit"
_TEMPWARNING_CSV_KEY = "Temperature warning"  # ignored
_OUTRANGE_CSV_KEY = "Out of target range"  # ignored
_OTHER_CSV_KEY = "Other"  # ignored
_BEFORE_MEAL_CSV_KEY = "Before meal"
_AFTER_MEAL_CSV_KEY = "After meal"
# Control test has extra whitespace which is not ignored.
_CONTROL_CSV_KEY = "Control test" + " " * 197

_DATE_FORMAT = "%d.%m.%Y"
_TIME_FORMAT = "%H:%M"

_DATETIME_FORMAT = " ".join((_DATE_FORMAT, _TIME_FORMAT))


class Device(driver.GlucometerDevice):
    def __init__(self, device: Optional[str]) -> None:
        if not device or not os.path.isdir(device):
            raise exceptions.CommandLineError(
                "--device parameter is required, should point to mount path "
                "for the meter."
            )

        reports_path = os.path.join(device, "*", "Reports", "*.csv")
        report_files = glob.glob(reports_path)
        if not report_files:
            raise exceptions.ConnectionFailed(
                f'No report file found in path "{reports_path}".'
            )

        self.report_file = report_files[0]

    def _get_records_reader(self) -> csv.DictReader:
        self.report.seek(0)
        # Skip the first two lines
        next(self.report)
        next(self.report)

        return csv.DictReader(
            self.report, delimiter=";", skipinitialspace=True, quoting=csv.QUOTE_NONE
        )

    def connect(self) -> None:
        self.report = open(self.report_file, "r", newline="\r\n", encoding="utf-8")

    def disconnect(self) -> None:
        self.report.close()

    def get_meter_info(self) -> common.MeterInfo:
        return common.MeterInfo(
            f"{self.get_model()} glucometer",
            serial_number=self.get_serial_number(),
            native_unit=self.get_glucose_unit(),
        )

    def get_model(self) -> str:
        # $device/MODEL/Reports/*.csv
        return os.path.basename(os.path.dirname(os.path.dirname(self.report_file)))

    def get_serial_number(self) -> str:
        self.report.seek(0)
        # ignore the first line.
        next(self.report)
        # The second line of the CSV is serial-no;report-date;report-time;;;;;;;
        return next(self.report).split(";")[0]

    def get_glucose_unit(self) -> common.Unit:
        # Get the first record available and parse that.
        record = next(self._get_records_reader())
        return _UNIT_MAP[record[_UNIT_CSV_KEY]]

    def get_datetime(self) -> NoReturn:
        raise NotImplementedError

    def _set_device_datetime(self, date: datetime.datetime) -> NoReturn:
        raise NotImplementedError

    def zero_log(self) -> NoReturn:
        raise NotImplementedError

    def _extract_datetime(
        self, record: dict[str, str]
    ) -> datetime.datetime:  # pylint: disable=no-self-use
        # Date and time are in separate column, but we want to parse them
        # together.
        date_and_time = " ".join((record[_DATE_CSV_KEY], record[_TIME_CSV_KEY]))
        return datetime.datetime.strptime(date_and_time, _DATETIME_FORMAT)

    def _extract_meal(
        self, record: dict[str, str]
    ) -> common.Meal:  # pylint: disable=no-self-use
        if record[_AFTER_MEAL_CSV_KEY] and record[_BEFORE_MEAL_CSV_KEY]:
            raise exceptions.InvalidResponse("Reading cannot be before and after meal.")
        elif record[_AFTER_MEAL_CSV_KEY]:
            return common.Meal.AFTER
        elif record[_BEFORE_MEAL_CSV_KEY]:
            return common.Meal.BEFORE
        else:
            return common.Meal.NONE

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        for record in self._get_records_reader():
            if record[_RESULT_CSV_KEY] is None:
                continue

            yield common.GlucoseReading(
                self._extract_datetime(record),
                common.convert_glucose_unit(
                    float(record[_RESULT_CSV_KEY]),
                    _UNIT_MAP[record[_UNIT_CSV_KEY]],
                    common.Unit.MG_DL,
                ),
                meal=self._extract_meal(record),
            )
