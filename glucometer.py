#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utility to manage glucometers' data."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import argparse
import importlib
import logging
import sys

from dateutil import parser as date_parser

from glucometerutils import common
from glucometerutils import exceptions

def main():
  parser = argparse.ArgumentParser()
  subparsers = parser.add_subparsers(dest="action")

  parser.add_argument(
    '--driver', action='store', required=True,
    help='Select the driver to use for connecting to the glucometer.')
  parser.add_argument(
    '--device', action='store', required=True,
    help='Select the path to the glucometer device.')

  parser.add_argument(
    '--vlog', action='store', required=False, type=int,
    help=('Python logging level. See the levels at '
          'https://docs.python.org/3/library/logging.html#logging-levels'))

  subparsers.add_parser(
    'info', help='Display information about the meter.')
  subparsers.add_parser(
    'zero', help='Zero out the data log of the meter.')

  parser_dump = subparsers.add_parser(
    'dump', help='Dump the readings stored in the device.')
  parser_dump.add_argument(
    '--unit', action='store', choices=common.VALID_UNITS,
    help='Select the unit to use for the dumped data.')
  parser_dump.add_argument(
    '--sort-by', action='store', default='timestamp',
    choices=common.Reading._fields,
    help='Field to order the dumped data by.')

  parser_date = subparsers.add_parser(
    'datetime', help='Reads or sets the date and time of the glucometer.')
  parser_date.add_argument(
    '--set', action='store', nargs='?', const='now', default=None,
    help='Set the date rather than just reading it from the device.')

  args = parser.parse_args()

  logging.basicConfig(level=args.vlog)

  driver = importlib.import_module('glucometerutils.drivers.' + args.driver)
  device = driver.Device(args.device)

  device.connect()
  device_info = device.get_meter_info()

  try:
    if args.action == 'info':
      try:
        time_str = device.get_datetime()
      except NotImplementedError:
        time_str = 'N/A'
      print("{device_info}Time: {time}".format(
        device_info=str(device_info), time=time_str))
    elif args.action == 'dump':
      unit = args.unit
      if unit is None:
        unit = device_info.native_unit

      readings = device.get_readings()

      if args.sort_by is not None:
        readings = sorted(
          readings, key=lambda reading: getattr(reading, args.sort_by))

      for reading in readings:
        print(reading.as_csv(unit))
    elif args.action == 'datetime':
      if args.set == 'now':
        print(device.set_datetime())
      elif args.set:
        try:
          print(device.set_datetime(date_parser.parse(args.set)))
        except ValueError:
          print('%s: not a valid date' % args.set, file=sys.stderr)
      else:
        print(device.get_datetime())
    elif args.action == 'zero':
      confirm = input('Delete the device data log? (y/N) ')
      if confirm.lower() in ['y', 'ye', 'yes']:
        device.zero_log()
        print('\nDevice data log zeroed.')
      else:
        print('\nDevice data log not zeroed.')
        return 1
    else:
      return 1
  except exceptions.Error as err:
    print('Error while executing \'%s\': %s' % (args.action, str(err)))
    return 1

  device.disconnect()

if __name__ == "__main__":
    main()
