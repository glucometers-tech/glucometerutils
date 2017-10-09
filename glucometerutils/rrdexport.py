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
databasefile = (filepath + "GlucoseDatabase.rrd")
htmlfile = (filepath + "glucose.html")


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
  print ("Verifying if databasefile " + str(databasefile) + " exist:")
  if os.path.isfile(databasefile):
            print ("Database File exists and is readable")
  else:
            print ("Database File is missing, creating new")
  #
  # create rrd database
  # "--start", "1483225201" means start rrd database at   01 Jan 2017
  # "--step", "1"          means one entry every seconds
  # "DS:glucose:GAUGE:86400:0:1000" means entrytablename glucose:Type Gauge:unknow after 86400 Seconds:min value 0: max value 1000
  # "RRA:MAX:0.5:1:200000" for Details see https://oss.oetiker.ch/rrdtool/tut/rrd-beginners.en.html 
  #
            ret = rrdtool.create (databasefile, "--start", "-180d", "--step", "1",
                                  "DS:glucose:GAUGE:86400:0:1000",
                                  "RRA:MAX:0.5:1:200000000")
  #   
  # Read Device
  #
  readings = device.get_readings()

  #   
  # Sort Entrys
  #
  if sort is not None:
   readings = sorted(
          readings, key=lambda reading: getattr(reading, sort))

  #   
  # load rrd tool import
  #
  from rrdtool import updatev as rrd_update

  #   
  # For Loop to use the Entrys
  #
  for reading in readings:
    epochtime = str(reading.timestamp.strftime('%s'))
    glucose = str(reading.value)
    rrdupdate_args = (epochtime + ":" + glucose)
    #
    # write Data to rrd database
    #
    try:
     ret = rrdtool.update (databasefile, rrdupdate_args) 
    except (rrdtool.OperationalError):
     print (rrdupdate_args + " rrdtool.OperationalError: Value already exist or is not writeable")
    except :
     print (rrdupdate_args + " Some Error is occured updating the RRD Database")
    else:
     print (rrdupdate_args + " RRD Update OK")
  #   
  # Create Graph for Last day
  #
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
  "DEF:glucose=" + databasefile + ":glucose:MAX",
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
