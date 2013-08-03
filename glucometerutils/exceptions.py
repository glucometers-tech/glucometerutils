"""Common exceptions for glucometerutils."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'GPL v3 or later'

class Error(Exception):
  """Base class for the errors."""


class InvalidResponse(Error):
  """The response received from the meter was not understood"""

  def __init__(self, response):
    self.response = response

  def __str__(self):
    return 'Invalid response received:\n%s' % self.response


class InvalidGlucoseUnit(Error):
  """Unable to parse the given glucose unit"""

  def __init__(self, unit):
    self.unit = unit

  def __str__(self):
    return 'Invalid glucose unit received:\n%s' % self.unit
