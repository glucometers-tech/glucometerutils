# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines for data in glucometers."""

import datetime
import enum
import textwrap
from collections.abc import Sequence
from typing import Any, Optional, Union

import attr


class Unit(enum.Enum):
    MG_DL = "mg/dL"
    MMOL_L = "mmol/L"


# Constants for meal information
class Meal(enum.Enum):
    NONE = ""
    BEFORE = "Before Meal"
    AFTER = "After Meal"


# Constants for measure method
class MeasurementMethod(enum.Enum):
    BLOOD_SAMPLE = "blood sample"
    CGM = "CGM"  # Continuous Glucose Monitoring
    TIME = "time"


def convert_glucose_unit(value: float, from_unit: Unit, to_unit: Unit) -> float:
    """Convert the given value of glucose level between units.

    Args:
      value: The value of glucose in the current unit
      from_unit: The unit value is currently expressed in
      to_unit: The unit to conver the value to: the other if empty.

    Returns:
      The converted representation of the blood glucose level.
    """
    from_unit = Unit(from_unit)
    to_unit = Unit(to_unit)

    if from_unit == to_unit:
        return value

    if from_unit == Unit.MG_DL:
        return round(value / 18.0, 2)

    return round(value * 18.0, 1)


@attr.s(auto_attribs=True)
class GlucoseReading:
    timestamp: datetime.datetime
    value: float
    meal: Meal = attr.ib(default=Meal.NONE, validator=attr.validators.in_(Meal))
    comment: str = ""
    measure_method: MeasurementMethod = attr.ib(
        default=MeasurementMethod.BLOOD_SAMPLE,
        validator=attr.validators.in_(MeasurementMethod),
    )
    extra_data: dict[str, Any] = attr.Factory(dict)

    def get_value_as(self, to_unit: Unit) -> float:
        """Returns the reading value as the given unit.

        Args:
          to_unit: The unit to return the value to.
        """
        return convert_glucose_unit(self.value, Unit.MG_DL, to_unit)

    def as_csv(self, unit: Unit) -> str:
        """Returns the reading as a formatted comma-separated value string."""
        return '"%s","%.2f","%s","%s","%s"' % (
            self.timestamp,
            self.get_value_as(unit),
            self.meal.value,
            self.measure_method.value,
            self.comment,
        )


@attr.s(auto_attribs=True)
class KetoneReading:
    timestamp: datetime.datetime
    value: float
    comment: str = ""
    measure_method: MeasurementMethod = attr.ib(
        default=MeasurementMethod.BLOOD_SAMPLE,
        validator=attr.validators.in_({MeasurementMethod.BLOOD_SAMPLE}),
    )
    extra_data: dict[str, Any] = attr.Factory(dict)

    def as_csv(self, unit: Unit) -> str:
        """Returns the reading as a formatted comma-separated value string."""
        del unit  # Unused for Ketone readings.

        return '"%s","%.2f","","%s","%s"' % (
            self.timestamp,
            self.value,
            self.measure_method.value,
            self.comment,
        )


@attr.s(auto_attribs=True)
class TimeAdjustment:
    timestamp: datetime.datetime
    old_timestamp: datetime.datetime
    measure_method: MeasurementMethod = attr.ib(
        default=MeasurementMethod.TIME, validator=attr.validators.in_(MeasurementMethod)
    )
    extra_data: dict[str, Any] = attr.Factory(dict)

    def as_csv(self, unit: Unit) -> str:
        del unit
        return '"%s","","","%s","%s"' % (
            self.timestamp,
            self.measure_method.value,
            self.old_timestamp,
        )


AnyReading = Union[GlucoseReading, KetoneReading, TimeAdjustment]


@attr.s(auto_attribs=True)
class MeterInfo:
    """General information about the meter.

    Attributes:
      model: Human readable model name, chosen by the driver.
      serial_number: Serial number identified for the reader (or N/A if not
        available in the protocol.)
      version_info: List of strings with any version information available about
        the device. It can include hardware and software version.
      native_unit: One of the Unit values to identify the meter native unit.
    """

    model: str
    serial_number: str = "N/A"
    version_info: Sequence[str] = ()
    native_unit: Unit = attr.ib(default=Unit.MG_DL, validator=attr.validators.in_(Unit))
    patient_name: Optional[str] = None

    def __str__(self) -> str:
        version_information_string = "N/A"
        if self.version_info:
            version_information_string = "\n                ".join(
                self.version_info
            ).strip()

        base_output = textwrap.dedent(
            f"""\
            {self.model}
            Serial Number: {self.serial_number}
            Version Information:
                {version_information_string}
            Native Unit: {self.native_unit.value}
        """
        )

        if self.patient_name is not None:
            base_output += f"Patient Name: {self.patient_name}\n"

        return base_output
