"""Common routines for data in glucometers."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

# Constants for units
UNIT_MGDL = 'mg/dL'
UNIT_MMOLL = 'mmol/L'

VALID_UNITS = [UNIT_MGDL, UNIT_MMOLL]

# Constants for date format
DATETIME_12HR = '12 hours'
DATETIME_24HR = '24 hours'

from glucometerutils import exceptions


def ConvertGlucoseUnit(value, from_unit, to_unit=None):
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
