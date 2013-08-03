#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utility to manage glucometers' data."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013, Diego Elio Pettenò'
__license__ = 'MIT'

import argparse
import importlib
import sys

from dateutil import parser as date_parser

from glucometerutils import common
from glucometerutils.drivers import otultra2

def main():
  parser = argparse.ArgumentParser()
  subparsers = parser.add_subparsers(dest="action")

  parser.add_argument(
    '--driver', action='store', required=True,
    help='Select the driver to use for connecting to the glucometer.')
  parser.add_argument(
    '--device', action='store', required=True,
    help='Select the path to the glucometer device.')

  parser_dump = subparsers.add_parser(
    'dump', help='Dump the readings stored in the device.')
  parser_dump.add_argument(
    '--unit', action='store', choices=common.VALID_UNITS,
    help='Select the unit to use for the dumped data.')

  parser_date = subparsers.add_parser(
    'datetime', help='Reads or sets the date and time of the glucometer.')
  parser_date.add_argument(
    '--set', action='store', nargs='?', const='now', default=None,
    help='Set the date rather than just reading it from the device.')

  args = parser.parse_args()

  driver = importlib.import_module('glucometerutils.drivers.' + args.driver)
  device = driver.Device(args.device)

  if args.action == 'dump':
    for reading in device.get_readings(args.unit):
      print('%s,%f' % reading)
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
  else:
    return 1

if __name__ == "__main__":
    main()
