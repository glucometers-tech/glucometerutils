# -*- coding: utf-8 -*-
"""Common exceptions for glucometerutils."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

class Error(Exception):
    """Base class for the errors."""


class CommandLineError(Error):
    """Error with commandline parameters provided."""


class ConnectionFailed(Error):
    """It was not possible to connect to the meter."""

    def __init__(self, message='Unable to connect to the meter.'):
        super(ConnectionFailed, self).__init__(message)


class CommandError(Error):
    """It was not possible to send a command to the device."""

    def __init__(self, message="Unable to send command to device."):
        super(CommandError, self).__init__(message)


class InvalidResponse(Error):
    """The response received from the meter was not understood"""

    def __init__(self, response):
        super(InvalidResponse, self).__init__(
            'Invalid response received:\n%s' % response)


class InvalidChecksum(InvalidResponse):
    def __init__(self, expected, received):
        super(InvalidChecksum, self).__init__(
            'Response checksum not matching: %08x expected, %08x received' %
            (expected, received))


class InvalidGlucoseUnit(Error):
    """Unable to parse the given glucose unit"""

    def __init__(self, unit):
        super(InvalidGlucoseUnit, self).__init__(
            'Invalid glucose unit received:\n%s' % unit)
