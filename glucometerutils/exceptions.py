# -*- coding: utf-8 -*-
"""Common exceptions for glucometerutils."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

class Error(Exception):
  """Base class for the errors."""

  def __str__(self):
    return self.message


class InvalidResponse(Error):
  """The response received from the meter was not understood"""

  def __init__(self, response):
    self.message = 'Invalid response received:\n%s' % response


class InvalidGlucoseUnit(Error):
  """Unable to parse the given glucose unit"""

  def __init__(self, unit):
    self.message = 'Invalid glucose unit received:\n%s' % unit
