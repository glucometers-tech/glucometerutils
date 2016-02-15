# -*- coding: utf-8 -*-
"""Common routines for data in glucometers."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import collections

from glucometerutils import exceptions

# Constants for units
UNIT_MGDL = 'mg/dL'
UNIT_MMOLL = 'mmol/L'

VALID_UNITS = [UNIT_MGDL, UNIT_MMOLL]

# Constants for meal information
NO_MEAL = ''
BEFORE_MEAL = 'Before Meal'
AFTER_MEAL = 'After Meal'

# Constants for date format
DATETIME_12HR = '12 hours'
DATETIME_24HR = '24 hours'


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
  '_ReadingBase', ['timestamp', 'value', 'meal', 'comment'])

class Reading(_ReadingBase):
  def __new__(cls, timestamp, value, meal=NO_MEAL, comment=''):
    """Constructor for the reading object.

    Args:
      timestamp: (datetime) Timestamp of the reading as reported by the meter.
      value: (float) Value of the reading, in mg/dL.
      meal: (string) Meal-relativeness as reported by the reader, if any.
      comment: (string) Comment reported by the reader, if any.

    The value is stored in mg/dL, even though this is not the standard value,
    because at least most of the LifeScan devices report the raw data in this
    format.
    """
    return super(Reading, cls).__new__(
      cls, timestamp=timestamp, value=value, meal=meal, comment=comment)

  def get_value_as(self, to_unit):
    """Returns the reading value as the given unit.

    Args:
      to_unit: (UNIT_MGDL|UNIT_MMOLL) The unit to return the value to.
    """
    return convert_glucose_unit(self.value, UNIT_MGDL, to_unit)
