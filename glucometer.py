#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utility to manage glucometers' data."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2013-2017, Diego Elio Pettenò'
__license__ = 'MIT'

import argparse
import importlib
import inspect
import logging
import sys
import rrdtool
import os.path
import os

from glucometerutils import common
from glucometerutils import exceptions

def openFile():
    fileName = listbox_1.get(ACTIVE)
    os.system("start " + fileName)

def rrdgraph():
    print ('rrdgraph funktion')


def main():
  if sys.version_info < (3, 2):
    raise Exception(
      'Unsupported Python version, please use at least Python 3.2')

  parser = argparse.ArgumentParser()
  subparsers = parser.add_subparsers(dest="action")

  parser.add_argument(
    '--driver', action='store', required=True,
    help='Select the driver to use for connecting to the glucometer.')
  parser.add_argument(
    '--device', action='store', required=False,
    help=('Select the path to the glucometer device. Some devices require this '
          'argument, others will try autodetection.'))

  parser.add_argument(
    '--vlog', action='store', required=False, type=int,
    help=('Python logging level. See the levels at '
          'https://docs.python.org/3/library/logging.html#logging-levels'))

  subparsers.add_parser(
    'help', help=('Display a description of the driver, including supported '
                  'features and known quirks.'))
  subparsers.add_parser(
    'info', help='Display information about the meter.')
  subparsers.add_parser(
    'zero', help='Zero out the data log of the meter.')
  #subparsers.add_parser(
  #  'rrdgraph1d', help='Create a Graph from the stored Values for the last day into the Homedirectory')
  subparsers.add_parser(
    'rrdgraph7d', help='Create a Graph from the stored Values for the last 7 days into the Homedirectory')

  parser_rrdgraph = subparsers.add_parser(
    'rrdgraph', help='Create a Graph from the stored Values for userdefined days into the Homedirectory. Use --start and --end for the Timeframe')
  parser_rrdgraph.add_argument(
    '--start', action='store', default='-1d',
    help='Startdate of the graph, default - 1 Day.')
  parser_rrdgraph.add_argument(
    '--end', action='store', default='now',
    help='enddate of the Graph, default now.')
  parser_rrdgraph.add_argument(
    '--file', action='store', default='lastday.png',
    help=('Filename to write the Graph, please use extension ".png", default "lastday.png".',
    'Example: "python3 glucometer.py --driver fslibre --device /dev/hidraw0 rrdgraph --start=-2d --end=-1d --file=test.png"',
    'use driver fslibre, device /dev/hidraw0, create rrdgraph with startdate minus 2 days from now, enddate minus 1 day from now to File test.png'))

  parser_rrd = subparsers.add_parser(
    'rrd', help='Read Data from Device, save to a RRDDatabase and create a Graph from the last day into the Homedirectory')
  parser_rrd.add_argument(
    '--unit', action='store', choices=common.VALID_UNITS,
    help='Select the unit to use for the dumped data.')
  parser_rrd.add_argument(
    '--sort-by', action='store', default='timestamp',
    choices=common.Reading._fields,
    help='Field to order the dumped data by.')

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

  from os.path import expanduser
  home = expanduser("~")

  try:
    driver = importlib.import_module('glucometerutils.drivers.' + args.driver)
  except ImportError as e:
    logging.error(
      'Error importing driver "%s", please check your --driver parameter:\n%s',
      args.driver, e)
    return 1

  # This check needs to happen before we try to initialize the device, as the
  # help action does not require a --device at all.
  if args.action == 'help':
    print(inspect.getdoc(driver))
    return 0

  elif args.action == 'rrdgraph':
      starttime = args.start
      endtime = args.end
      outputfile = args.file
      rrdgraphic = (home + "/" + outputfile)
      print ( "rrdgraph start " + starttime + " end " + endtime + " File " + rrdgraphic)
      ret = rrdtool.graph( rrdgraphic, "--imgformat", "PNG",
      "--start", starttime, "--end", endtime,
      "--width", "1000", "--heigh", "350", "--slope-mode",
      "--lower-limit", "0", "--upper-limit", "300", 
      "--title", "Blood Sugar - Glucose", "--vertical-label", "mg/dl",
      "DEF:bloodsugar=blutzucker_60.rrd:bloodsugar:MAX",
      #"CDEF:mmol=bloodsugar,0.0555,*",
      "CDEF:x1=bloodsugar,179,GT,bloodsugar,UNKN,IF",
      "CDEF:x2=bloodsugar,79,GT,bloodsugar,UNKN,IF",
      "CDEF:x3=bloodsugar,0,GT,bloodsugar,UNKN,IF",
      "VDEF:Last=bloodsugar,LAST", "VDEF:First=bloodsugar,FIRST",
      "AREA:180#CCFFFF", "AREA:80#e5e5e5",
      "GPRINT:bloodsugar:LAST:\\tCur\: %5.2lf\\t",
      "GPRINT:bloodsugar:AVERAGE:\\tAvg\: %5.2lf\\t",
      "GPRINT:bloodsugar:MAX:\\tMax\: %5.2lf\\t",
      "GPRINT:bloodsugar:MIN:\\tMin\: %5.2lf\\n", "LINE2:180#ff8080:Critical\\r", "LINE2:80#8080ff:Warning \\r",
      "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b",
      #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
      "GPRINT:First:von %d.%m.%Y %H\:%M   --:strftime", "GPRINT:Last:bis %d.%m.%Y %H\:%M\\c:strftime",
      "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
      )
      print ("the Graph is created: " + rrdgraphic )
      os.system("gwenview " + rrdgraphic)
      return 0

      return 0 
  
  #
  # Argument rrdgraph7d
  #
  elif args.action == 'rrdgraph7d':
      outputfile = "last7day.png"
      rrdgraphic = (home + "/" + outputfile)
      ret = rrdtool.graph( rrdgraphic, "--imgformat", "PNG",
      "--start", "-7d", "--end", "now",
      "--width", "1000", "--heigh", "350", "--slope-mode",
      "--lower-limit", "0", "--upper-limit", "300",
      "--title", "Blood Sugar - Glucose", "--vertical-label", "mg/dl",
      "DEF:bloodsugar=blutzucker_60.rrd:bloodsugar:MAX",
      #"CDEF:mmol=bloodsugar,0.0555,*",
      "CDEF:x1=bloodsugar,179,GT,bloodsugar,UNKN,IF",
      "CDEF:x2=bloodsugar,79,GT,bloodsugar,UNKN,IF",
      "CDEF:x3=bloodsugar,0,GT,bloodsugar,UNKN,IF",
      "VDEF:Last=bloodsugar,LAST", "VDEF:First=bloodsugar,FIRST",
      "AREA:180#CCFFFF", "AREA:80#e5e5e5",
      "GPRINT:bloodsugar:LAST:\\tCur\: %5.2lf\\t",
      "GPRINT:bloodsugar:AVERAGE:\\tAvg\: %5.2lf\\t",
      "GPRINT:bloodsugar:MAX:\\tMax\: %5.2lf\\t",
      "GPRINT:bloodsugar:MIN:\\tMin\: %5.2lf\\n", "LINE2:180#ff8080:Critical\\r", "LINE2:80#8080ff:Warning \\r",
      "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b",
      #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
      "GPRINT:First:von %d.%m.%Y %H\:%M   --:strftime", "GPRINT:Last:bis %d.%m.%Y %H\:%M\\c:strftime",
      "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
      )
      print ("Graph last7days.png create in your homefolder " + home )
      os.system("gwenview " + rrdgraphic)
      return 0


  # Initialize Device
  #

  device = driver.Device(args.device)

  device.connect()
  device_info = device.get_meter_info()

  try:
#   
# Argument Info
#
    if args.action == 'info':
      try:
        time_str = device.get_datetime()
      except NotImplementedError:
        time_str = 'N/A'
      print("{device_info}Time: {time}".format(
        device_info=str(device_info), time=time_str))
#
# Argument DUMP
#
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
#   
# Argument DateTime
#
    elif args.action == 'datetime':
      if args.set == 'now':
        print(device.set_datetime())
      elif args.set:
        try:
          from dateutil import parser as date_parser
          new_date = date_parser.parse(args.set)
        except ImportError:
          logging.error(
            'Unable to import module "dateutil", please install it.')
          return 1
        except ValueError:
          logging.error('%s: not a valid date', args.set)
          return 1
        print(device.set_datetime(new_date))
      else:
        print(device.get_datetime())
#   
# Argument Zero
#
    elif args.action == 'zero':
      confirm = input('Delete the device data log? (y/N) ')
      if confirm.lower() in ['y', 'ye', 'yes']:
        device.zero_log()
        print('\nDevice data log zeroed.')
      else:
        print('\nDevice data log not zeroed.')
        return 1
#   
# Argument rrd
#
    elif args.action == 'rrd':
    #
    #verify if rrd database exist
    #
      #import os.path
      PATH = 'blutzucker_60.rrd'
      print ("Verifying if File " + str(PATH) + " exist:")
      if os.path.isfile(PATH):
            print ("File exists and is readable")
      else:
            print ("File is missing")
    #
    # if not create rrd database
    # "--start", "1483225201" means start rrd database at   01 Jan 2017
    # "--step", "60"          means one entry every 60 seconds
    # "DS:bloodsugar:GAUGE:86400:0:1000" means entrytablename bloodsugar:Type Gauge:unknow after 86400 Seconds:min value 0: max value 1000
    # "RRA:MAX:0.5:1:200000" means ???
    #
            ret = rrdtool.create (PATH, "--start", "1483225201", "--step", "60",
                                  "DS:bloodsugar:GAUGE:86400:0:1000",
                                  "RRA:MAX:0.5:1:200000")
    #  from rrdtool import updatev as rrd_update
    #
    # Verify bloodsugar unit mg/dl or mmol/l
    #
      unit = args.unit
      if unit is None:
        unit = device_info.native_unit
        readings = device.get_readings()

      if args.sort_by is not None:
        readings = sorted(
          readings, key=lambda reading: getattr(reading, args.sort_by))

      for reading in readings:
          epochtime = str(reading.timestamp.strftime('%s'))
          bloodsugar = str(reading.value)
    #
    # write Data to rrd database
    #
          from rrdtool import updatev as rrd_update
          rrdupdate_args = (epochtime + ":" + bloodsugar)
          print (rrdupdate_args)
          try:
            ret = rrdtool.update (PATH, rrdupdate_args) 
          except (rrdtool.OperationalError):
            print ("rrdtool.OperationalError: Value exist")
          except :
            print ("Some Error is occured updating the RRD Database")
          else:
            print ("RRD Update OK")
      #help(rrdtool.lastupdate)
      #from os.path import expanduser
      #home = expanduser("~")
      rrdgraphic = (home + "/lastday.png")
      ret = rrdtool.graph( rrdgraphic,
      "--start", "-1d", "--end", "now",
      "--width", "1000", "--heigh", "350",
      "--lower-limit", "0", "--upper-limit", "400",
      "--title", "Blood Sugar - Glucose", "--vertical-label", "mg/dl",
      "DEF:bloodsugar=blutzucker_60.rrd:bloodsugar:MAX",
      #"CDEF:mmol=bloodsugar,18.02,/",
      "CDEF:x1=bloodsugar,179,GT,bloodsugar,UNKN,IF",
      "CDEF:x2=bloodsugar,79,GT,bloodsugar,UNKN,IF",
      "CDEF:x3=bloodsugar,0,GT,bloodsugar,UNKN,IF",
      "GPRINT:bloodsugar:LAST:Cur\: %5.2lf",
      "GPRINT:bloodsugar:AVERAGE:Avg\: %5.2lf",
      "GPRINT:bloodsugar:MAX:Max\: %5.2lf",
      "GPRINT:bloodsugar:MIN:Min\: %5.2lf",
      "AREA:180#CCFFFF", "AREA:80#e5e5e5",
      "LINE2:180#ff8080:Critical", "LINE2:80#8080ff:Warning",
      "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b", 
      #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
      "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
      )
      return 1
    else:
      return 1
  except exceptions.Error as err:
    print('Error while executing \'%s\': %s' % (args.action, str(err)))
    return 1

  device.disconnect()

if __name__ == "__main__":
    main()
