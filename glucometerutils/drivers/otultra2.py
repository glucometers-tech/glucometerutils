# -*- coding: utf-8 -*-
"""Driver for LifeScan OneTouch Ultra 2 devices"""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import datetime
import re

import serial

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.drivers import lifescan_common


class Device(object):
  def __init__(self, device):
    self.serial_ = serial.Serial(
      port=device, baudrate=9600, bytesize=serial.EIGHTBITS,
      parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
      timeout=1, xonxoff=False, rtscts=False, dsrdtr=False, writeTimeout=None)

  def _send_command(self, cmd):
    """Send command interface.

    Args:
      cmd: command and parameters to send (without newline)

    This function exists to wrap the need to send the 0x11 0x0d prefix with
    each command that wakes this model up.
    """
    cmdstring = bytes('\x11\r' + cmd + '\r', 'ascii')
    self.serial_.write(cmdstring);
    self.serial_.flush()

  _RESPONSE_MATCH = re.compile(r'^(.+) ([0-9A-F]{4})\r$')

  def _validate_and_strip_checksum(self, line):
    """Verify the CRC16 checksum and remove it from the line.

    Args:
      line: the line to check the CRC16 of.

    Returns:
      A copy of the line with the CRC16 stripped out.
    """
    match = self._RESPONSE_MATCH.match(line)

    if not match:
      raise lifescan_common.MissingChecksum(line)

    response, checksum_string = match.groups()

    try:
      checksum_given = int(checksum_string, 16)
      checksum_calculated = lifescan_common.calculate_checksum(
        bytes(response, 'ascii'))

      if checksum_given != checksum_calculated:
        raise lifescan_common.InvalidChecksum(checksum_given,
                                              checksum_calculated)
    except ValueError:
      raise lifescan_common.InvalidChecksum(checksum_given,
                                            None)

    return response

  def _send_oneliner_command(self, cmd):
    """Send command and read a one-line response.

    Args:
      cmd: command and parameters to send (without newline)

    Returns:
      A single line of text that the glucometer responds, without the checksum.
    """
    self._send_command(cmd)

    line = self.serial_.readline().decode('ascii')
    return self._validate_and_strip_checksum(line)

  def get_information_string(self):
    """Returns a single string with all the identification information.

    Returns:
      A string including the serial number, software version, date and time and
      default unit.
    """
    return ('OneTouch Ultra 2 glucometer\n'
            'Serial number: %s\n'
            'Software version: %s\n'
            'Time: %s\n'
            'Default unit: %s' % (
              self.get_serial_number(),
              self.get_version(),
              self.get_datetime(),
              self.get_glucose_unit()))

  def get_version(self):

    """Returns an identifier of the firmware version of the glucometer.

    Returns:
      The software version returned by the glucometer, such as
        "P02.00.00 30/08/06".
    """
    response = self._send_oneliner_command('DM?')

    if response[0] != '?':
      raise exceptions.InvalidResponse(response)

    return response[1:]

  _SERIAL_NUMBER_RE = re.compile('^@ "([A-Z0-9]{9})"$')

  def get_serial_number(self):
    """Retrieve the serial number of the device.

    Returns:
      A string representing the serial number of the device.

    Raises:
      exceptions.InvalidResponse: if the DM@ command returns a string not
        matching _SERIAL_NUMBER_RE.
      InvalidSerialNumber: if the returned serial number does not match
        the OneTouch2 device as per specs.
    """
    response = self._send_oneliner_command('DM@')

    match = self._SERIAL_NUMBER_RE.match(response)
    if not match:
      raise exceptions.InvalidResponse(response)

    serial_number = match.group(1)

    # 'Y' at the far right of the serial number is the indication of a OneTouch
    # Ultra2 device, as per specs.
    if serial_number[-1] != 'Y':
      raise lifescan_common.InvalidSerialNumber(serial_number)

    return serial_number

  # The [TF] at the start is to accept both Get (F) and Set (T) commands.
  _DATETIME_RE = re.compile(
    r'^"[A-Z]{3}","([0-9]{2}/[0-9]{2}/[0-9]{2})","([0-9]{2}:[0-9]{2}:[0-9]{2})   "$')

  def _parse_datetime(self, response):
    """Convert a response with date and time from the meter into a datetime.

    Args:
      response: the response coming from a DMF or DMT command

    Returns:
      A datetime object built according to the returned response.

    Raises:
      InvalidResponse if the string cannot be matched by _DATETIME_RE.
    """
    match = self._DATETIME_RE.match(response)
    if not match:
      raise exceptions.InvalidResponse(response)

    date, time = match.groups()
    month, day, year = [int(part) for part in date.split('/')]
    hour, minute, second = [int(part) for part in time.split(':')]

    # Yes, OneTouch2's firmware is not Y2K safe.
    return datetime.datetime(2000 + year, month, day, hour, minute, second)

  def get_datetime(self):
    """Returns the current date and time for the glucometer.

    Returns:
      A datetime object built according to the returned response.
    """
    response = self._send_oneliner_command('DMF')
    return self._parse_datetime(response[2:])

  def set_datetime(self, date=datetime.datetime.now()):
    """Sets the date and time of the glucometer.

    Args:
      date: The value to set the date/time of the glucometer to. If none is
        given, the current date and time of the computer is used.

    Returns:
      A datetime object built according to the returned response.
    """
    response = self._send_oneliner_command(
      'DMT' + date.strftime('%m/%d/%y %H:%M:%S'))

    return self._parse_datetime(response[2:])

  def zero_log(self):
    """Zeros out the data log of the device.

    This function will clear the memory of the device deleting all the readings
    in an irrecoverable way.
    """
    response = self._send_oneliner_command('DMZ')
    if response != 'Z':
      raise exceptions.InvalidResponse(response)

  def _parse_glucose_unit(self, unit):

    """Parses the value of a OneTouch Ultra Glucose unit definition.

    Args:
      unit: the string reported by the glucometer as glucose unit.

    Return:
      common.UNIT_MGDL: if the glucometer reads in mg/dL
      common.UNIT_MMOLL: if the glucometer reads in mmol/L

    Raises:
      exceptions.InvalidGlucoseUnit: if the unit is not recognized
    """
    if unit == 'MG/DL ':
      return common.UNIT_MGDL
    elif unit == 'MMOL/L':
      return common.UNIT_MMOLL
    else:
      raise exceptions.InvalidGlucoseUnit(string)

  _GLUCOSE_UNIT_RE = re.compile(r'^SU\?,"(MG/DL |MMOL/L)"')

  def get_glucose_unit(self):
    """Returns a constant representing the unit for the dumped readings.

    Returns:
      common.UNIT_MGDL: if the glucometer reads in mg/dL
      common.UNIT_MMOLL: if the glucometer reads in mmol/L
    """
    response = self._send_oneliner_command('DMSU?')

    match = self._GLUCOSE_UNIT_RE.match(response)
    return self._parse_glucose_unit(match.group(1))

  _DUMP_HEADER_RE = re.compile(r'P ([0-9]{3}),"[0-9A-Z]{9}","(?:MG/DL |MMOL/L)"')
  _DUMP_LINE_RE = re.compile(
    r'P (?P<datetime>"[A-Z]{3}","[0-9/]{8}","[0-9:]{8}   "),'
    r'"(?P<control>[C ]) (?P<value>[0-9]{3})(?P<parityerror>[\? ])",'
    r'"(?P<meal>[NBA])","(?P<comment>0[0-9]|1[01])", 00')

  def get_readings(self):
    """Iterates over the reading values stored in the glucometer.

    Args:
      unit: The glucose unit to use for the output.

    Yields:
      A tuple (date, value) of the readings in the glucometer. The value is a
      floating point in the unit specified; if no unit is specified, the default
      unit in the glucometer will be used.

    Raises:
      exceptions.InvalidResponse: if the response does not match what expected.
    """
    self._send_command('DMP')
    data = self.serial_.readlines()

    header = data.pop(0).decode('ascii')
    match = self._DUMP_HEADER_RE.match(header)
    if not match:
      raise exceptions.InvalidResponse(header)

    count = int(match.group(1))
    assert count == len(data)

    for line in data:
      line = self._validate_and_strip_checksum(line.decode('ascii'))

      match = self._DUMP_LINE_RE.match(line)
      if not match:
        raise exceptions.InvalidResponse(line)

      line_data = match.groupdict()

      date = self._parse_datetime(line_data['datetime'])
      meal = self._MEAL_CODES[line_data['meal']]
      comment = self._COMMENT_CODES[line_data['comment']]

      # OneTouch2 always returns the data in mg/dL even if the glucometer is set
      # to mmol/L, so there is no conversion required.
      yield common.Reading(
        date, float(line_data['value']), meal=meal, comment=comment)

  # The following two hashes are taken directly from LifeScan's documentation
  _MEAL_CODES = {
    'N': '',
    'B': 'Before Meal',
    'A': 'After Meal',
  }

  _COMMENT_CODES = {
    '00': '',  # would be 'No Comment'
    '01': 'Not Enough Food',
    '02': 'Too Much Food',
    '03': 'Mild Exercise',
    '04': 'Hard Exercise',
    '05': 'Medication',
    '06': 'Stress',
    '07': 'Illness',
    '08': 'Feel Hypo',
    '09': 'Menses',
    '10': 'Vacation',
    '11': 'Other',
  }
