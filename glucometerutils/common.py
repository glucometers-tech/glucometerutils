# -*- coding: utf-8 -*-
"""Common routines for data in glucometers."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import collections
import textwrap

from glucometerutils import exceptions

# Constants for units
UNIT_MGDL = 'mg/dL'
UNIT_MMOLL = 'mmol/L'

VALID_UNITS = [UNIT_MGDL, UNIT_MMOLL]

# Constants for meal information
NO_MEAL = ''
BEFORE_MEAL = 'Before Meal'
AFTER_MEAL = 'After Meal'

# Constants for measure method
BLOOD_SAMPLE = 'blood sample'
CGM = 'CGM' # Continuous Glucose Monitoring


def convert_glucose_unit(value, from_unit, to_unit=None):
  """Convert the given value of glucose level between units.

  Args:
    value: The value of glucose in the current unit
    from_unit: The unit value is currently expressed in
    to_unit: The unit to conver the value to: the other if empty.

  Returns:
    The converted representation of the blood glucose level.

  Raises:
    exceptions.InvalidGlucoseUnit: If the parameters are incorrect.
  """
  if from_unit not in VALID_UNITS:
    raise exceptions.InvalidGlucoseUnit(from_unit)

  if from_unit == to_unit:
    return value

  if to_unit is not None:
    if to_unit not in VALID_UNITS:
      raise exceptions.InvalidGlucoseUnit(to_unit)

  if from_unit is UNIT_MGDL:
    return round(value / 18.0, 2)
  else:
    return round(value * 18.0, 0)

_ReadingBase = collections.namedtuple(
  '_ReadingBase', ['timestamp', 'value', 'comment', 'measure_method'])

class GlucoseReading(_ReadingBase):
  def __new__(cls, timestamp, value, meal=NO_MEAL, comment='',
              measure_method=BLOOD_SAMPLE):
    """Constructor for the glucose reading object.

    Args:
      timestamp: (datetime) Timestamp of the reading as reported by the meter.
      value: (float) Value of the reading, in mg/dL.
      meal: (string) Meal-relativeness as reported by the reader, if any.
      comment: (string) Comment reported by the reader, if any.
      measure_method: (string) Measure method as reported by the reader if any,
        assuming blood sample otherwise.

    The value is stored in mg/dL, even though this is not the standard value,
    because at least most of the LifeScan devices report the raw data in this
    format.
    """
    instance = super(GlucoseReading, cls).__new__(
      cls, timestamp=timestamp, value=value, comment=comment,
      measure_method=measure_method)
    setattr(instance, 'meal', meal)
    return instance

  def get_value_as(self, to_unit):
    """Returns the reading value as the given unit.

    Args:
      to_unit: (UNIT_MGDL|UNIT_MMOLL) The unit to return the value to.
    """
    return convert_glucose_unit(self.value, UNIT_MGDL, to_unit)

  def as_csv(self, unit):
    """Returns the reading as a formatted comma-separated value string."""
    return '"%s","%.2f","%s","%s","%s"' % (
      self.timestamp, self.get_value_as(unit), self.meal, self.measure_method,
      self.comment)

class KetoneReading(_ReadingBase):
  def __new__(cls, timestamp, value, comment='', **kwargs):
    """Constructor for the ketone reading object.

    Args:
      timestamp: (datetime) Timestamp of the reading as reported by the meter.
      value: (float) Value of the reading, in mmol/L.
      comment: (string) Comment reported by the reader, if any.

    The value is stored in mg/dL, even though this is not the standard value,
    because at least most of the LifeScan devices report the raw data in this
    format.
    """
    return super(KetoneReading, cls).__new__(
      cls, timestamp=timestamp, value=value, comment=comment,
      measure_method=BLOOD_SAMPLE)

  def get_value_as(self, *args):
    """Returns the reading value in mmol/L."""
    return self.value

  def as_csv(self, unit):
    """Returns the reading as a formatted comma-separated value string."""
    return '"%s","%.2f","%s","%s"' % (
      self.timestamp, self.get_value_as(unit), self.measure_method,
      self.comment)


_MeterInfoBase = collections.namedtuple(
  '_MeterInfoBase', ['model', 'serial_number', 'version_info', 'native_unit'])

class MeterInfo(_MeterInfoBase):
  def __new__(cls, model, serial_number='N/A', version_info=(),
              native_unit=UNIT_MGDL):
    """Construct a meter information object.

    Args:
      model: (string) Human-readable model name, depending on driver.
      serial_number: (string) Optional serial number to identify the device.
      version_info: (list(string)) Optional hardware/software version information.
      native_unit: (UNIT_MGDL|UNIT_MMOLL) Native unit of the device for display.
    """
    return super(MeterInfo, cls).__new__(
      cls, model=model, serial_number=serial_number, version_info=version_info,
      native_unit=native_unit)

  def __str__(self):
    version_information_string = 'N/A'
    if self.version_info:
      version_information_string = '\n    '.join(self.version_info).strip()

    return textwrap.dedent("""\
      {model}
      Serial Number: {serial_number}
      Version Information:
          {version_information_string}
      Native Unit: {native_unit}
      """).format(model=self.model, serial_number=self.serial_number,
                  version_information_string=version_information_string,
                  native_unit=self.native_unit)
