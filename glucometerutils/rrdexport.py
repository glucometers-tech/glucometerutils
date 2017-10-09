# -*- coding: utf-8 -*-
"""Common routines for use of export to rrd database in glucometers.""" 

__author__ = 'Florian Ballangó'
__email__ = 'florianballango@gmx.de'
__copyright__ = 'Copyright © 2017, Florian Ballangó'
__license__ = 'MIT'


import rrdtool
import os.path
import os
#import subprocess
import webbrowser


from os.path import expanduser
home = expanduser("~")
filepath = (home + "/glucometerutils/")
Databasefile = (filepath + "GlucoseDatabase.rrd")


def rrdgraph():
    print ('rrdgraph funktion')
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

def rrdgraph1d(unit,starttime,endtime,outputfile):
    #if args.action == 'rrdgraph':
      #starttime = args.start
      #endtime = args.end
      #outputfile = args.file
      rrdgraphic = (filepath + outputfile)
      print ( "rrdgraph start " + starttime + " end " + endtime + " File " + rrdgraphic)
      ret = rrdtool.graph( rrdgraphic, "--imgformat", "PNG",
      "--start", starttime, "--end", endtime,
      "--width", "1000", "--heigh", "350", "--slope-mode",
      "--lower-limit", "0", "--upper-limit", "300", 
      "--title", "Blood Sugar - Glucose", "--vertical-label", "mg/dl",
      "DEF:glucose=" + Databasefile + ":glucose:MAX:step=60",
      "CDEF:mmol=glucose,0.0555,*",
      "CDEF:x1=glucose,179,GT,glucose,UNKN,IF",
      "CDEF:x2=glucose,79,GT,glucose,UNKN,IF",
      "CDEF:x3=glucose,0,GT,glucose,UNKN,IF",
      "VDEF:Last=glucose,LAST", "VDEF:First=glucose,FIRST",
      "AREA:180#CCFFFF", "AREA:80#e5e5e5",
      "GPRINT:glucose:LAST:\\tCur\: %5.2lf mg/dl\\t",
      "GPRINT:glucose:AVERAGE:\\tAvg\: %5.2lf mg/dl\\t",
      "GPRINT:glucose:MAX:\\tMax\: %5.2lf mg/dl\\t",
      "GPRINT:glucose:MIN:\\tMin\: %5.2lf mg/dl\\n", "GPRINT:mmol:AVERAGE:\\tAvg\: %5.2lf mmol/l\\n",
      "LINE2:180#ff8080:Critical\\r", "LINE2:80#8080ff:Warning \\r",
      "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b",
      #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
      "GPRINT:First:von %d.%m.%Y %H\:%M   --:strftime", "GPRINT:Last:bis %d.%m.%Y %H\:%M\\c:strftime",
      "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
      )
      print ("the Graph is created: " + rrdgraphic )
      #os.system("gwenview " + rrdgraphic + "&")
      #subprocess.call([rrdgraphic])
      webbrowser.open(rrdgraphic)
      return 0

def rrdgraph7d(unit):  
  #
  # Argument rrdgraph7d
  #
  #  elif args.action == 'rrdgraph7d':
      i = 1
      j = 0
      #if j == 0
       #j = "1s"
      while i <= 7:
         print(i)
         outputfile = "last" + str(i) + "day.png"
         rrdgraphic = (filepath + outputfile)
         ret = rrdtool.graph( rrdgraphic, "--imgformat", "PNG",
         "--start", "-" + str(i) + "d", "--end", "-" + str(j) + "d",
         "--width", "1000", "--heigh", "350", "--slope-mode",
         "--lower-limit", "0", "--upper-limit", "300",
         "--title", "Blood Sugar - Glucose", "--vertical-label", "mg/dl",
         "DEF:glucose=" + Databasefile + ":glucose:MAX:step=60",
         "CDEF:mmol=glucose,0.0555,*",
         "CDEF:x1=glucose,179,GT,glucose,UNKN,IF",
         "CDEF:x2=glucose,79,GT,glucose,UNKN,IF",
         "CDEF:x3=glucose,0,GT,glucose,UNKN,IF",
         "VDEF:Last=glucose,LAST", "VDEF:First=glucose,FIRST",
         "AREA:180#CCFFFF", "AREA:80#e5e5e5",
         "GPRINT:glucose:LAST:\\tCur\: %5.2lf\\t",
         "GPRINT:glucose:AVERAGE:\\tAvg\: %5.2lf\\t",
         "GPRINT:glucose:MAX:\\tMax\: %5.2lf\\t",
         "GPRINT:glucose:MIN:\\tMin\: %5.2lf\\t", "GPRINT:mmol:AVERAGE:\\tAvg mmol/l\: %5.2lf\\n",
         "LINE2:180#ff8080:Critical\\r", "LINE2:80#8080ff:Warning \\r",
         "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b",
         #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
         "GPRINT:First:von %d.%m.%Y %H\:%M   --:strftime", "GPRINT:Last:bis %d.%m.%Y %H\:%M\\c:strftime",
         "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
         )
         j = i
         i += 1
      #print ("Graph last7days.png create in your homefolder " + home )
      #os.system("gwenview " + rrdgraphic)
      webbrowser.open(filepath + "Glucometer.html")
      return 0
  


    
def dumprrd(device,unit,sort):

  #
  # Verify Path and database file
  #
  
  print ("Verifying if Folder " + str(filepath) + " exist:")
  if not os.path.exists(filepath):
          print ("Path is missing, creating Folder glucometerutils")
          os.makedirs(filepath)
  #
  #verify if rrd database exist
  #
  print ("Verifying if Databasefile " + str(Databasefile) + " exist:")
  if os.path.isfile(Databasefile):
            print ("Database File exists and is readable")
  else:
            print ("Database File is missing, creating new")
  #
  # create rrd database
  # "--start", "1483225201" means start rrd database at   01 Jan 2017
  # "--step", "1"          means one entry every seconds
  # "DS:glucose:GAUGE:86400:0:1000" means entrytablename glucose:Type Gauge:unknow after 86400 Seconds:min value 0: max value 1000
  # "RRA:MAX:0.5:1:200000" means ???
  #
            ret = rrdtool.create (Databasefile, "--start", "1483225201", "--step", "1",
                                  "DS:glucose:GAUGE:86400:0:1000",
                                  "RRA:MAX:0.5:1:200000000")
  #   
  # Argument rrd
  #
  
  #  from rrdtool import updatev as rrd_update
  #
  # Verify glucose unit mg/dl or mmol/l
  #
  #unit = args.unit
  #if unit is None:
  #      unit = device_info.native_unit

  readings = device.get_readings()

  if sort is not None:
   readings = sorted(
          readings, key=lambda reading: getattr(reading, sort))

  for reading in readings:
    epochtime = str(reading.timestamp.strftime('%s'))
    glucose = str(reading.value)
    #
    # write Data to rrd database
    #
    from rrdtool import updatev as rrd_update
    rrdupdate_args = (epochtime + ":" + glucose)
    print (rrdupdate_args)
    try:
     ret = rrdtool.update (Databasefile, rrdupdate_args) 
    except (rrdtool.OperationalError):
     print ("rrdtool.OperationalError: Value exist")
    except :
     print ("Some Error is occured updating the RRD Database")
  else:
     print ("RRD Update OK")
  #help(rrdtool.lastupdate)
  starttime = "-1d"
  endtime = "now"
  outputfile = ("Graph" + starttime + "_" + endtime + ".png" )
  rrdgraphic = (filepath + outputfile)
  print ( "rrdgraph start " + starttime + " end " + endtime + " File " + rrdgraphic)
  ret = rrdtool.graph( rrdgraphic, "--imgformat", "PNG",
  "--start", starttime, "--end", endtime,
  "--width", "1000", "--heigh", "350", "--slope-mode",
  "--lower-limit", "0", "--upper-limit", "300",
  "--title", "Blood Sugar - Glucose", "--vertical-label", unit,
  "DEF:glucose=" + Databasefile + ":glucose:MAX",
  "CDEF:mmol=glucose,0.0555,*",
  "CDEF:x1=glucose,179,GT,glucose,UNKN,IF",
  "CDEF:x2=glucose,79,GT,glucose,UNKN,IF",
  "CDEF:x3=glucose,0,GT,glucose,UNKN,IF",
  "VDEF:Last=glucose,LAST", "VDEF:First=glucose,FIRST",
  "AREA:180#CCFFFF", "AREA:80#e5e5e5",
  "GPRINT:glucose:LAST:\\tCur\: %5.2lf\\t",
  "GPRINT:glucose:AVERAGE:\\tAvg\: %5.2lf\\t",
  "GPRINT:glucose:MAX:\\tMax\: %5.2lf\\t",
  "GPRINT:glucose:MIN:\\tMin\: %5.2lf\\t", "GPRINT:mmol:AVERAGE:\\tAvg mmol/l\: %5.2lf\\n",
  "LINE2:180#ff8080:Critical\\r", "LINE2:80#8080ff:Warning \\r",
  "LINE3:x3#FF0000", "LINE3:x2#000000", "LINE3:x1#ff951b",
  #"LINE1:mmol#ff0000:mmol/l", "--right-axis-label", "mmol/l",
  "GPRINT:First:von %d.%m.%Y %H\:%M   --:strftime", "GPRINT:Last:bis %d.%m.%Y %H\:%M\\c:strftime",
  "--color", "BACK#FFFFFF", "--color", "CANVAS#e5e5e5", "--color", "SHADEB#9999CC"
  )
  print ("the Graph is created: " + rrdgraphic )
  #os.system("gwenview " + rrdgraphic)
  webbrowser.open(rrdgraphic)
  return 0
