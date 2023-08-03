# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2017 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Base driver for FreeStyle Libre devices.

This module provides the common driver functionality supported for Libre and Libre2.

Protocol documentation available at
https://protocols.glucometers.tech/abbott/freestyle-libre
"""

import datetime
import logging
from collections.abc import Generator, Mapping, Sequence
from typing import Optional

from glucometerutils import common, exceptions
from glucometerutils.support import freestyle

# Fields of the records returned by both $history and $arresult?
# Tuple of pairs of idx and field name
_BASE_ENTRY_MAP = (
    (0, "device_id"),
    (1, "type"),
    (2, "month"),
    (3, "day"),
    (4, "year"),  # 2-digits
    (5, "hour"),
    (6, "minute"),
    (7, "second"),
)

# Fields of the records returned by $history?
_HISTORY_ENTRY_MAP = _BASE_ENTRY_MAP + (
    (13, "value"),
    (15, "errors"),
)

# Fields of the results returned by $arresult? where type = 2
_ARRESULT_TYPE2_ENTRY_MAP = (
    (9, "reading-type"),  # 0 = glucose blood strip,
    # 1 = ketone blood strip,
    # 2 = glucose sensor
    (12, "value"),
    (15, "sport-flag"),
    (16, "medication-flag"),
    (17, "rapid-acting-flag"),  # see _ARRESULT_RAPID_INSULIN_ENTRY_MAP
    (18, "long-acting-flag"),
    (19, "custom-comments-bitfield"),
    (23, "double-long-acting-insulin"),
    (25, "food-flag"),
    (26, "food-carbs-grams"),
    (28, "errors"),
)

_ARRESULT_TIME_ADJUSTMENT_ENTRY_MAP = (
    (9, "old_month"),
    (10, "old_day"),
    (11, "old_year"),
    (12, "old_hour"),
    (13, "old_minute"),
    (14, "old_second"),
)

# Fields only valid when rapid-acting-flag is "1"
_ARRESULT_RAPID_INSULIN_ENTRY_MAP = ((43, "double-rapid-acting-insulin"),)


def _parse_record(
    record: Sequence[str], entry_map: Sequence[tuple[int, str]]
) -> dict[str, int]:
    """Parses a list of string fields into a dictionary of integers."""

    if not record:
        return {}

    try:
        return {key: int(record[idx]) for idx, key in entry_map}
    except IndexError:
        return {}


def _extract_timestamp(
    parsed_record: Mapping[str, int], prefix: str = ""
) -> datetime.datetime:
    """Extract the timestamp from a parsed record.

    This leverages the fact that all the records have the same base structure.
    """

    return datetime.datetime(
        parsed_record[prefix + "year"] + 2000,
        parsed_record[prefix + "month"],
        parsed_record[prefix + "day"],
        parsed_record[prefix + "hour"],
        parsed_record[prefix + "minute"],
        parsed_record[prefix + "second"],
    )


def _parse_arresult(record: Sequence[str]) -> Optional[common.AnyReading]:
    """Takes an array of string fields as input and parses it into a Reading."""

    parsed_record = _parse_record(record, _BASE_ENTRY_MAP)

    # There are other record types, but we don't currently need to expose these.
    if not parsed_record:
        return None
    elif parsed_record["type"] == 2:
        parsed_record.update(_parse_record(record, _ARRESULT_TYPE2_ENTRY_MAP))
    elif parsed_record["type"] == 5:
        parsed_record.update(_parse_record(record, _ARRESULT_TIME_ADJUSTMENT_ENTRY_MAP))
        return common.TimeAdjustment(
            _extract_timestamp(parsed_record),
            _extract_timestamp(parsed_record, "old_"),
            extra_data={"device_id": parsed_record["device_id"]},
        )
    else:
        return None

    # Check right away if we have rapid insulin
    if parsed_record["rapid-acting-flag"]:
        parsed_record.update(_parse_record(record, _ARRESULT_RAPID_INSULIN_ENTRY_MAP))

    if parsed_record["errors"]:
        return None

    comment_parts = []
    measure_method: Optional[common.MeasurementMethod] = None
    cls: Optional[type[common.AnyReading]] = None
    value: Optional[float] = None

    if parsed_record["reading-type"] == 2:
        comment_parts.append("(Scan)")
        measure_method = common.MeasurementMethod.CGM
        cls = common.GlucoseReading
        value = parsed_record["value"]
    elif parsed_record["reading-type"] == 0:
        comment_parts.append("(Blood)")
        measure_method = common.MeasurementMethod.BLOOD_SAMPLE
        cls = common.GlucoseReading
        value = parsed_record["value"]
    elif parsed_record["reading-type"] == 1:
        comment_parts.append("(Ketone)")
        measure_method = common.MeasurementMethod.BLOOD_SAMPLE
        cls = common.KetoneReading
        # automatically convert the raw value in mmol/L
        raw_value = parsed_record["value"]
        if raw_value is None:
            raise ValueError(f"Invalid Ketone value: {parsed_record!r}")
        value = freestyle.convert_ketone_unit(raw_value)
    else:
        # unknown reading
        return None

    custom_comments = record[29:35]
    for comment_index in range(6):
        if parsed_record["custom-comments-bitfield"] & (1 << comment_index):
            comment_parts.append(custom_comments[comment_index])

    if parsed_record["sport-flag"]:
        comment_parts.append("Sport")

    if parsed_record["medication-flag"]:
        comment_parts.append("Medication")

    if parsed_record["food-flag"]:
        grams = parsed_record["food-carbs-grams"]
        if grams:
            comment_parts.append(f"Food ({grams} g)")
        else:
            comment_parts.append("Food")

    if parsed_record["long-acting-flag"]:
        insulin = parsed_record["double-long-acting-insulin"] / 2
        if insulin:
            comment_parts.append(f"Long-acting insulin ({insulin:.1f})")
        else:
            comment_parts.append("Long-acting insulin")

    if parsed_record["rapid-acting-flag"]:
        # This record does not always exist, so calculate it only when present.
        if "double-rapid-acting-insulin" in parsed_record:
            rapid_insulin = parsed_record["double-rapid-acting-insulin"] / 2
            comment_parts.append(f"Rapid-acting insulin ({rapid_insulin:.1f})")
        else:
            comment_parts.append("Rapid-acting insulin")

    reading = cls(
        _extract_timestamp(parsed_record),
        value,
        comment="; ".join(comment_parts),
        measure_method=measure_method,
        extra_data={"device_id": parsed_record["device_id"]},
    )

    return reading


class LibreDevice(freestyle.FreeStyleHidDevice):
    """Glucometer driver for FreeStyle Libre devices."""

    _MODEL_NAME: str

    def get_meter_info(self) -> common.MeterInfo:
        """Return the device information in structured form."""
        return common.MeterInfo(
            self._MODEL_NAME,
            serial_number=self.get_serial_number(),
            version_info=("Software version: " + self._get_version(),),
            native_unit=self.get_glucose_unit(),
            patient_name=self.get_patient_name(),
        )

    def get_serial_number(self) -> str:
        """Overridden function as the command is not compatible."""
        return self._session.send_text_command(b"$sn?").rstrip("\r\n")

    def get_glucose_unit(self) -> common.Unit:  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""
        uom = self._session.send_text_command(b"$uom?").rstrip("\r\n")
        if uom == "0":
            return common.Unit.MMOL_L
        if uom == "1":
            return common.Unit.MG_DL

        raise exceptions.InvalidGlucoseUnit(uom)

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        # First of all get the usually longer list of sensor readings, and
        # convert them to Readings objects.
        for record in self._session.query_multirecord(b"$history?"):
            parsed_record = _parse_record(record, _HISTORY_ENTRY_MAP)

            if not parsed_record or parsed_record["errors"] != 0:
                # The reading is considered invalid, so ignore it.
                continue

            yield common.GlucoseReading(
                _extract_timestamp(parsed_record),
                parsed_record["value"],
                comment="(Sensor)",
                measure_method=common.MeasurementMethod.CGM,
                extra_data={"device_id": parsed_record["device_id"]},
            )

        # Then get the results of explicit scans and blood tests (and other
        # events).
        for record in self._session.query_multirecord(b"$arresult?"):
            logging.debug(f"Retrieved arresult: {record!r}")
            reading = _parse_arresult(record)
            if reading:
                yield reading

    def zero_log(self) -> None:
        self._session.send_text_command(b"$resetpatient")
