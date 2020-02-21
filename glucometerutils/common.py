# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines for data in glucometers."""

import datetime
import enum
import textwrap
from typing import Optional, Sequence

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


def convert_glucose_unit(value, from_unit, to_unit):
    # type: (float, Unit, Unit) -> float
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

    return round(value * 18.0, 0)


@attr.s
class GlucoseReading:

    timestamp = attr.ib(type=datetime.datetime)
    value = attr.ib(type=float)
    meal = attr.ib(default=Meal.NONE, validator=attr.validators.in_(Meal), type=Meal)
    comment = attr.ib(default="", type=str)
    measure_method = attr.ib(
        default=MeasurementMethod.BLOOD_SAMPLE,
        validator=attr.validators.in_(MeasurementMethod),
        type=MeasurementMethod,
    )
    extra_data = attr.ib(factory=dict)

    def get_value_as(self, to_unit):
        # type: (Unit) -> float
        """Returns the reading value as the given unit.

        Args:
          to_unit: (Unit) The unit to return the value to.
        """
        return convert_glucose_unit(self.value, Unit.MG_DL, to_unit)

    def as_csv(self, unit):
        # type: (Unit) -> str
        """Returns the reading as a formatted comma-separated value string."""
        return '"%s","%.2f","%s","%s","%s"' % (
            self.timestamp,
            self.get_value_as(unit),
            self.meal.value,
            self.measure_method.value,
            self.comment,
        )


@attr.s
class KetoneReading:

    timestamp = attr.ib(type=datetime.datetime)
    value = attr.ib(type=float)
    comment = attr.ib(default="", type=str)
    extra_data = attr.ib(factory=dict)

    def as_csv(self, unit):
        """Returns the reading as a formatted comma-separated value string."""
        del unit  # Unused for Ketone readings.

        return '"%s","%.2f","%s","%s"' % (
            self.timestamp,
            self.value,
            MeasurementMethod.BLOOD_SAMPLE.value,
            self.comment,
        )


@attr.s
class TimeAdjustment:
    timestamp = attr.ib()  # type: datetime.datetime
    old_timestamp = attr.ib()  # type: datetime.datetime
    measure_method = attr.ib(
        default=MeasurementMethod.TIME, validator=attr.validators.in_(MeasurementMethod)
    )  # type: MeasurementMethod
    extra_data = attr.ib(factory=dict)

    def as_csv(self, unit):
        del unit
        return '"%s","","%s","%s"' % (
            self.timestamp,
            self.measure_method.value,
            self.old_timestamp,
        )


@attr.s
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

    model = attr.ib(type=str)
    serial_number = attr.ib(default="N/A", type=str)
    version_info = attr.ib(default=(), type=Sequence[str])
    native_unit = attr.ib(
        default=Unit.MG_DL, validator=attr.validators.in_(Unit), type=Unit
    )
    patient_name = attr.ib(default=None, type=Optional[str])

    def __str__(self):
        version_information_string = "N/A"
        if self.version_info:
            version_information_string = "\n    ".join(self.version_info).strip()

        base_output = textwrap.dedent(
            """\
            {model}
            Serial Number: {serial_number}
            Version Information:
                {version_information_string}
            Native Unit: {native_unit}
        """
        ).format(
            model=self.model,
            serial_number=self.serial_number,
            version_information_string=version_information_string,
            native_unit=self.native_unit.value,
        )

        if self.patient_name != None:
            base_output += "Patient Name: {patient_name}\n".format(
                patient_name=self.patient_name
            )

        return base_output
