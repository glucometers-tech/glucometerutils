#!/usr/bin/env python3
# -*- coding: utf-8 -*-
''' Utility to convert data from a glucometer into charts. '''
__author__  = 'Timothy Allen'
__email__   = 'tim@treehouse.org.za'
__license__ = 'MIT'

''' Included are the OpenSans and IcoGluco font sets.
    IcoGluco contains fonts from Noto Sans, which is licensed under the
    SIL Open Font License version 1.1
    <http://scripts.sil.org/cms/scripts/page.php?site_id=nrsi&id=OFL>,
    as well as a green apple character from
    Vectors Market <https://www.flaticon.com/authors/vectors-market>,
    licensed under Creative Commons BY 3.0, <http://creativecommons.org/licenses/by/3.0/>, and
    syringe and pushpin characters from FreePik, <http://www.freepik.com>,
    licensed under Creative Commons BY 3.0, <http://creativecommons.org/licenses/by/3.0/>.
'''

# TODO: weekly graph with each day's figures as a different-coloured line
# TODO: Split each type of charts into a separate function and offer a means
#       of selecting which charts to generate

import argparse
import csv
import datetime as dt
from matplotlib import rcParams
from matplotlib.figure import Figure
from matplotlib.backends.backend_pdf import FigureCanvasPdf as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages as FigurePDF
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib import dates as mdates
from matplotlib import font_manager as fm
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path
from matplotlib import ticker as mticker
import numpy as np
import os
import re
from scipy import interpolate
from scipy.special import binom
import sys

''' Constants for units '''
UNIT_MGDL = 'mg/dL'
UNIT_MMOLL = 'mmol/L'
VALID_UNITS = [UNIT_MGDL, UNIT_MMOLL]

''' When averaging, set the period to this number of minutes '''
INTERVAL = 15
''' Set the default high and low in mmol/L; it will be reset to mg/dL if neccessary '''
DEFAULT_HIGH = 8
DEFAULT_LOW  = 4
''' Maximum glucose value to display '''
GRAPH_MAX_MMOLL = 21
GRAPH_MIN_MMOLL = 0
GRAPH_MAX_MGDL  = 400
GRAPH_MIN_MGDL  = 0

''' Colour for below-target maxmins '''
RED = '#d71920'
'''' Colour for above-target maxmins '''
YELLOW = '#f1b80e'
''' Colour for graph lines  '''
BLUE = '#02538f'
''' Colour for median glucose box '''
GREEN = '#009e73'
''' Colour for median A1c box '''
BOXYELLOW = '#e69f00'

def main():
  if sys.version_info < (3, 2):
    raise Exception(
      'Unsupported Python version, please use at least Python 3.2')

  args = parse_arguments()

  ''' This could be done directly from glucometerutils instead of via CSV '''
  with open(args.input_file, 'r', newline='') as f:
     rows = from_csv(f)

  ''' Skip ketone entries '''
  rketones = re.compile('Ketone', flags=re.IGNORECASE);
  for row in rows:
    if rketones.search(row.get('measure_method')):
      rows.remove(row);
    elif rketones.search(row.get('comment')):
      rows.remove(row);

  ''' Skip finger stick test entries '''
  rfinger = re.compile('Blood', flags=re.IGNORECASE);
  if not args.fingerstick:
    for row in rows:
      if rfinger.search(row.get('comment')):
        rows.remove(row);

  for row in rows:
    row = parse_entry(row, args.icons)

  ''' Ensure that the rows are sorted by date '''
  rows = sorted(rows, key=lambda row: row.get('date'), reverse=False)

  ''' Fill in gaps that might exist in the data, in order to smooth the curves and fills '''
  ''' We're using 10 minute gaps in order to have more accurate fills '''
  rows = fill_gaps(rows, interval=dt.timedelta(minutes=10))

  ''' If we're on the default values for units, highs and lows, check that the average
      value is under 35 (assuming that average mmol/L < 35 and average mg/dL > 35) '''
  if args.units == UNIT_MMOLL and (args.high == DEFAULT_HIGH or args.low == DEFAULT_LOW):
    mean = round(np.mean([l.get('value') for l in rows]), 1)
    if mean > 35:
      args.units = UNIT_MGDL
      args.high  = convert_glucose_unit(args.high, UNIT_MMOLL)
      args.low   = convert_glucose_unit(args.low, UNIT_MMOLL)
      ''' Manually specify max and min for mg/dL '''
      args.graph_max = GRAPH_MAX_MGDL
      args.graph_min = GRAPH_MIN_MGDL

  ''' Set some defaults '''
  rcParams['font.size'] = 8
  rcParams['axes.titlesize'] = 12
  rcParams['font.family'] = 'sans-serif'
  rcParams['font.sans-serif'] = ['Calibri','Verdana','Geneva','Arial','Helvetica','DejaVu Sans','Bitstream Vera Sans','sans-serif']
  rcParams['mathtext.default'] = 'regular'

  ''' Load custom fonts for the icon sets
      At present, backend_pdf does not parse unicode correctly, and unicode
      characters from many fonts that lack proper glyph names are massed together
      and printed as the same character. The IcoGluco font, generated from Noto Sans and
      custom icons on IcoMoon, works around this. '''
  if args.icons:
    args.customfont = import_font('fonts/icogluco.ttf')
    #args.customfont = import_font('fonts/OpenSansEmoji.ttf') # Alternate font

  ''' Calculate the days and weeks in which we are interested '''
  ''' Note that trim_weeks should be adjusted based on the interval passed to fill_gaps() '''
  (days, weeks) = list_days_and_weeks(rows, trim_weeks=300)
  totalweeks = sum([len(weeks[y]) for y in weeks])
  totaldays  = len(days)

  nrows = args.graphs_per_page
  ncols = 1
  plotnum = 1
  with FigurePDF(args.output_file) as pdf:

    ''' Overall averages for all data by hour of the day '''
    start    = rows[0].get('date')
    end      = rows[-1].get('date')
    period   = start.strftime('%A, %-d %B %Y') + ' to ' + end.strftime('%A, %-d %B %Y')
    title    = 'Overall Average Glucose Summary for ' + period

    data = {}
    for row in rows:
      mpdate = dt.datetime.combine(rows[0]['date'], row.get('date').time())
      data[mdates.date2num(mpdate)] = {
        'value'   : row.get('value'),
        'comment' : row.get('comment'),
      }

    ''' Calculate max and min values for each 15 minute interval across the data set '''
    intervals = calculate_max_min(rows)
    intervaldata = {}
    for i in intervals:
      mpdate = dt.datetime.combine(rows[0]['date'], i)
      intervaldata[mdates.date2num(mpdate)] = {
        'max'   : intervals.get(i).get('max'),
        'min'   : intervals.get(i).get('min'),
      }

    ''' Calculate the mean and median blood glucose and HbA1c levels '''
    (g_mean, g_median, a_mean, a_median) = calculate_averages(data, args)

    figure = Figure(figsize=args.pagesize)
    canvas = FigureCanvas(figure)

    ax = figure.add_subplot(nrows, ncols, plotnum)
    ax.set_title(title)
    figure.set_tight_layout({'pad':3})

    ''' Draw the target range '''
    ax.axhspan(args.low, args.high, facecolor='#0072b2', edgecolor='#a8a8a8', alpha=0.1, zorder=15)

    ''' The maxmin fill (maximum and minimum values for each 15 minute
        period of the data set, by day) '''
    generate_plot(intervaldata,
         ax=ax,
         transforms={'spline':True, 'maxmin':True},
         args=args,
         color='#979797',
    )

    ''' The graph with a bezier curve applied, and a boundary transform to change line colour
        above and below the target values '''
    generate_plot(data,
        ax=ax,
        transforms={'bezier':True, 'avga1c':a_median, \
            'color':[RED, BLUE, RED], 'boundaries':[args.graph_min, args.low, args.high, args.graph_max]},
        args=args,
        color=BLUE,
    )

    ''' Save the graph to the output PDF if we're at the end of the page '''
    pdf.savefig(figure)
    ax.clear()


    ''' Overall averages for a week by hour of the dday '''
    cnt = 0
    for year in reversed(sorted(weeks.keys())):
      for week in reversed(sorted(weeks[year].keys())):
        ''' Turn the year into a date (the first week of the year is the one containing January 4th) '''
        time     = dt.datetime.combine(dt.date(year, 1, 4), dt.time(0, 0, 0))
        monday   = time + dt.timedelta(days=-time.weekday(), weeks=week-1)
        sunday   = monday + dt.timedelta(days=6)
        period   = monday.strftime('%A, %-d %B %Y') + ' to ' + sunday.strftime('%A, %-d %B %Y');
        title    = 'Average Glucose for ' + period

        weekrows = []
        for row in rows:
          for dow in range(7):
            day = monday + dt.timedelta(days=dow)
            if row.get('date').date() == day.date():
              weekrows.append(row)

        data = {}
        for row in weekrows:
          mpdate = dt.datetime.combine(monday, row.get('date').time())
          data[mdates.date2num(mpdate)] = {
            'value'   : row.get('value'),
            'comment' : row.get('comment'),
          }

        ''' Calculate the maximum and minimum value for each 15-minute period
            of the day, across the week '''
        intervals = calculate_max_min(weekrows)
        intervaldata = {}
        for i in intervals:
          mpdate = dt.datetime.combine(monday.date(), i)
          intervaldata[mdates.date2num(mpdate)] = {
            'max'   : intervals.get(i).get('max'),
            'min'   : intervals.get(i).get('min'),
          }

        ''' Calculate the mean and median blood glucose levels for the week '''
        (g_mean, g_median, a_mean, a_median) = calculate_averages(data, args)

        if cnt % nrows == 0:
          figure = Figure(figsize=args.pagesize)
          canvas = FigureCanvas(figure)

        plotnum = (cnt % nrows) + 1
        ax = figure.add_subplot(nrows, ncols, plotnum)
        ax.set_title(title)
        figure.set_tight_layout({'pad':3})

        ''' Draw the target range '''
        ax.axhspan(args.low, args.high, facecolor='#0072b2', edgecolor='#a8a8a8', alpha=0.1, zorder=15)

        ''' The maxmin fill of maximum and minimum values '''
        generate_plot(intervaldata,
            ax=ax,
            transforms={'spline':True, 'maxmin':True, 'avga1c':a_median},
            args=args,
            color='#979797',
        )

        ''' The graph with a bezier curve applied, and a boundary transform to change line colour
            above and below the target values '''
        generate_plot(data,
            ax=ax,
            transforms={'bezier':True, \
                'color':[RED, BLUE, RED], 'boundaries':[args.graph_min, args.low, args.high, args.graph_max]},
            args=args,
            color=BLUE,
        )

        ''' Save the graph to the output PDF if we're at the end of the page or at the end of the data '''
        if (cnt + 1) % nrows == 0 or (cnt + 1) == totalweeks:
          pdf.savefig(figure)
          ax.clear()
        cnt += 1

    ''' Daily graphs '''
    cnt = 0
    for day in reversed(sorted(days.keys())):
      title = 'Daily Glucose Summary for ' + day.strftime('%A, %-d %B %Y')

      data = {}
      for row in rows:
        if row.get('date').date() == day.date():
          mpdate = dt.datetime.combine(day.date(), row.get('date').time())
          data[mdates.date2num(mpdate)] = {
              'value'   : row.get('value'),
              'comment' : row.get('comment'),
          }

      ''' Calculate the mean and median blood glucose levels for the day '''
      (g_mean, g_median, a_mean, a_median) = calculate_averages(data, args)

      if cnt % nrows == 0:
        figure = Figure(figsize=args.pagesize)
        canvas = FigureCanvas(figure)

      plotnum = (cnt % nrows) + 1
      ax = figure.add_subplot(nrows, ncols, plotnum)
      ax.set_title(title)
      figure.set_tight_layout({'pad':3})

      ''' Draw the target range '''
      ax.axhspan(args.low, args.high, facecolor='#0072b2', edgecolor='#a8a8a8', alpha=0.2, zorder=15)

      ''' Draw graph with a spline tranform and labels '''
      generate_plot(data,
          ax=ax,
          transforms={'spline':True, 'label':True, 'avgglucose':g_median},
          args=args,
          color=BLUE,
          )

      ''' Fill the chart with colour when line is higher or lower than target range '''
      generate_plot(data,
          ax=ax,
          transforms={'spline':True, 'fill':True},
          args=args,
          )

      ''' Save the graph to the output PDF if we're at the end of the page '''
      if (cnt + 1) % nrows == 0 or (cnt + 1) == totaldays:
        pdf.savefig(figure)
        ax.clear()
      cnt += 1

  return 1


def generate_plot(data, ax=None, transforms={}, args=[], **plot_args):
  (x, y, z, p, q) = (list(), list(), list(), list(), list())
  for (key, value) in sorted(data.items()):
    ''' Time '''
    a = key
    if 'maxmin' in transforms:
      ''' If a max and a min exists, initialise them to y and z '''
      b = value.get('max')
      c = value.get('min')
    else:
      ''' Glucose and comment '''
      b = value.get('value')
      c = value.get('comment', '')
    x.append(a)
    y.append(b)
    z.append(c)

  x = np.asarray(x)
  y = np.asarray(y)
  ''' Don't convert z to a numpy array if it has text in it '''
  if len(z) > 0 and isinstance(z[0], (int, float)):
    z = np.asarray(z)

  ''' Calculations the axis limits '''
  firstminute = mdates.num2date(x[0]).replace(hour=0, minute=0, second=0, microsecond=0)
  lastminute  = mdates.num2date(x[-1]).replace(hour=23, minute=59, second=59, microsecond=59)
  x_min       =  mdates.date2num(firstminute)
  x_max       =  mdates.date2num(lastminute)
  ax.set_xlim(x_min, x_max)
  ax.set_ylim(args.graph_min, args.graph_max)
  ''' Calculate the time intervals in 2 hour segments '''
  xtimes = []
  time = firstminute
  while time < lastminute:
      xtimes.append(time)
      time += dt.timedelta(hours=2)
  if args.units == UNIT_MMOLL:
    y_tick_freq = 2
  else:
    y_tick_freq = 50

  ''' Formatting for axis labels, using date calculations from above '''
  ax.set_xlabel('Time', fontsize=9)
  ax.set_xbound(firstminute, lastminute)
  ax.grid(axis='x', color = '#f0f0f0', zorder=5)
  ax.set_xticks(xtimes)
  ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
  ax.xaxis.set_ticks_position('none')
  for tick in ax.xaxis.get_major_ticks():
    tick.label1.set_horizontalalignment('left')

  ax.set_ylabel('Blood Glucose (' + args.units + ')', fontsize=9)
  ax.set_ybound(args.graph_min, args.graph_max)
  ax.grid(axis='y', color = '#d0d0d0', linestyle = (1,(0.5,2)), zorder=5)
  ax.set_yticks([a for a in range(int(args.graph_min), int(args.graph_max), int(y_tick_freq))])
  ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d"))
  ax.yaxis.set_ticks_position('none')


  if 'maxmin' in transforms and transforms.get('maxmin') is True:
    maxmin = True
  else:
    maxmin = False

  ''' Transform points to apply smoothing and other fixups '''
  for transform in transforms:
    if transform == 'linear' and transforms.get(transform) is True:
      ''' Use SciPy's interp1d for linear transforming '''
      if not maxmin:
        f = interpolate.interp1d(x, y, kind='linear')
        ''' 50 is number of points to make between x.max & x.min '''
        x = np.linspace(x.min(), x.max(), 50)
        y = f(x)

    elif transform == 'spline' and transforms.get(transform) is True:
      ''' Use SciPy's UnivariateSpline for transforming (s is transforming factor) '''
      ''' An s of 8 (mmol/L) or 200 (mg/dL) was chosen by experimentation! '''
      if args.units == UNIT_MMOLL:
        s = 8
      else:
        s = 200
      if not maxmin:
        curve = interpolate.UnivariateSpline(x=x, y=y, k=3, s=s)
        y = curve(x)

    elif transform == 'bezier' and transforms.get(transform) is True:
      ''' Create bezier function for transforming (s is transforming factor) '''
      def bezier(points, s=100):
        n = len(points)
        b = [binom(n - 1, i) for i in range(n)]
        r = np.arange(n)
        for t in np.linspace(0, 1, s):
          u = np.power(t, r) * np.power(1 - t, n - r - 1) * b
          yield t, u @ points

      ''' The binomial calculation for the bezier curve overflows with arrays of 1020 or more elements,
          For large arrays, get a smaller slice of the full array.
          Do this by removing every nth element from the array. '''
      n = 5
      while len(x) > 1000:
        x = np.delete(x, np.arange(0, len(x), n), axis=0)
        y = np.delete(y, np.arange(0, len(y), n), axis=0)

      if not maxmin:
        curve = np.array([c for _, c in bezier(np.array([x,y]).T, 250)])
        (x, y) = (curve[:,0], curve[:,1])

    ''' Add the mean or median glucose and A1c values in an annotation box '''
    if transform == 'avgglucose' and isinstance(transforms.get(transform), (int, float)):
      if args.units == UNIT_MMOLL:
        gmtext = 'Median glucose: %.1f%s' % (round(transforms.get('avgglucose'), 1), args.units)
      else:
        gmtext = 'Median glucose: %.0f%s' % (round(transforms.get('avgglucose'), 1), args.units)

      ax.annotate(gmtext, fontsize=9, xy=(0.95, 0.85),
          xycoords='axes fraction', verticalalignment='top', horizontalalignment='right',
          zorder=60, bbox=dict(facecolor=GREEN, edgecolor='#009e73', alpha=0.7, pad=8),
          )
    if transform == 'avga1c' and isinstance(transforms.get(transform), (int, float)):
      ax.annotate('Median HbA1c: %.1f%%' % round(transforms.get('avga1c'), 1), fontsize=9,
          xy=(0.05, 0.85), xycoords='axes fraction',
          verticalalignment='top', horizontalalignment='left',
          zorder=60, bbox=dict(facecolor=BOXYELLOW, edgecolor='#e69f00', alpha=0.7, pad=8),
          )

    if args.units == UNIT_MMOLL:
      y_offset = 6
    else:
      y_offset = convert_glucose_unit(6, UNIT_MMOLL)

    if transform == 'label' and transforms.get(transform) is True and args.icons is True:
      for x_pos, y_pos, label in zip(x, y, z):
        if isinstance(label, dict) and len(label) > 0:
          symbol = '$'
          for key in label:
            ''' In the included IcoGluco font use for args.customfont,
                \N{SYRINGE} is a straight syringe (modified from FreePik) for rotated labels,
                \N{PUSHPIN} is a an angled syringe (from FreePik) for horizontal labels,
                \N{DAGGER} is unused (reserved a different syringe icon),
                \N{GREEN APPLE} is an apple (from Vectors Market). '''
            if key == 'Insulin':
              if isinstance(label.get(key), str):
                symbol += '\N{SYRINGE}^{%s}' % label.get(key)
                #symbol += '\N{PUSHPIN}^{%s}' % label.get(key)
                #symbol += '\N{SYRINGE}'
              else:
                symbol += '\N{SYRINGE}'
            elif key == 'Food':
              symbol += '\N{GREEN APPLE}'
          symbol += '$'
          ax.annotate(symbol, xy=(x_pos, args.graph_max-y_offset),
              rotation=45, zorder=40, fontsize=10,
              fontproperties=args.customfont,
            )

    ''' Create a line coloured according to the list in transforms['color'] '''
    if transform == 'boundaries' and 'color' in transforms:
      cmap = ListedColormap(transforms.get('color'))
      norm = BoundaryNorm(transforms.get('boundaries'), cmap.N)
      ''' create an array of points on the plot, and split into segments '''
      p = np.array([x, y]).T.reshape(-1, 1, 2)
      segments = np.concatenate([p[:-1], p[1:]], axis=1)
      ''' Colour the line according to the values in norm and the colours in cmap '''
      lc = LineCollection(segments, cmap=cmap, norm=norm, alpha=1, zorder=30)
      lc.set_array(y)


  if 'boundaries' in transforms and 'color' in transforms:
    ax.add_collection(lc)

  elif 'fill' in transforms and transforms.get('fill') is True:
    z = np.clip(y, None, args.high)
    ax.fill_between(x, y, z, interpolate=True, facecolor=YELLOW, alpha=0.7, zorder=20, **plot_args)

    z = np.clip(y, args.low, None)
    ax.fill_between(x, y, z, interpolate=True, facecolor=RED, alpha=0.7, zorder=20, **plot_args)

  elif maxmin:
    ax.fill_between(x, y, z, interpolate=True, alpha=0.5, zorder=10, **plot_args)

  else:
    ax.plot(x, y, '-', alpha=1, zorder=30, **plot_args)

  return ax

def import_font(fontname):
  ''' Turns a relative font path into a matplotlib font property. '''
  basedir  = os.path.dirname(os.path.abspath(__file__))
  fontpath = os.path.join(basedir, fontname)
  if not os.path.exists(fontpath):
    raise UserError("Font %s does not exist" % fontpath)
  prop = fm.FontProperties(fname=fontpath)
  return prop

def parse_entry(data, icons, fmt='%Y-%m-%d %H:%M:%S'):
  ''' Parse a row to create the icons and modify the timestamp

  Args:
    data: a dict containing the entries 'timestamp' and 'comment'
    icons: bool indicating whether to display food/injection icons on the graph
    date_format: the format of the timestamp in data

  Returns:
    data: the modified dict

  Raises:
      ValueError if an incorrectly-formatted date exists in data['timestamp']
  '''
  if icons:
    ''' Ignore comments that aren't relevant '''
    rrelevant    = re.compile('(Food|Rapid-acting insulin|Long-acting insulin)(?: \((.*?)\))', flags=re.IGNORECASE)
    rduplicate   = re.compile('^(I\$\^\{\d+\S?)(\}.*)$')
    commentparts = {}
    if data.get('comment') is not None:
      for part in data.get('comment').split('; '):
        relevant   = rrelevant.search(part)
        if relevant is not None:
          ctype  = relevant.group(1)
          cvalue = relevant.group(2)

          ''' Convert floating point-style strings (2.0) to integer-style strings (2) '''
          try:
            if int(float(cvalue)) == float(cvalue):
              cvalue = int(float(cvalue))
            else:
              cvalue = float(cvalue)
          except:
            pass
          cvalue = str(cvalue)

          if re.search('Rapid', ctype) is not None:
            cvalue += 'R'
          if re.search('Long', ctype) is not None:
            cvalue += 'L'

          ctype = re.sub('Rapid-acting insulin', 'Insulin', ctype, flags=re.IGNORECASE)
          ctype = re.sub('Long-acting insulin',  'Insulin', ctype, flags=re.IGNORECASE)

          if ctype in commentparts:
            commentparts[ctype] = commentparts[ctype] + '/' + cvalue
          else:
            commentparts[ctype] = cvalue

      data['comment'] = commentparts
    else:
      data['comment'] = {}

  ''' Convert timestamp to ISO8601 (by default, at least), and store datetime object '''
  try:
    date = dt.datetime.strptime(data.get('timestamp'), fmt)
    data['date'] = date
  except ValueError:
    raise ValueError('Invalid date: %s (should be of format %s)' % (data.get('timestamp'), fmt))
  data['timestamp'] = date.strftime('%Y-%m-%dT%H:%M:%S')

  ''' Convert value from string to float '''
  data['value'] = float(data.get('value'))

  # XXX convert everything to mg/dL for testing
  #data['value'] = float(round(data.get('value') * 18.0, 0))

  return data

def list_days_and_weeks(data, trim_weeks=192):
  ''' Create a dictionary of the days and weeks that occur in the CSV

  Args:
    data: a dict containing a 'timestamp' entry
    trim_weeks: the minimum number of entries a week should have in order to be considered for
      a weekly average graph. A reading taken every 15 minutes over two days would yield 192 readings.

  Returns:
    seendays: a dict containing all days in data
    seenweeks: a dict containing all weeks in data, subdivided by year
  '''
  seenweeks = {}
  seendays  = {}
  for d in data:
    date = d.get('date')
    day  = dt.datetime.combine(date.date(), dt.time.min)
    (year, week, weekday) = date.isocalendar()

    if not year in seenweeks:
      seenweeks[year] = {}
    if not week in seenweeks[year]:
      seenweeks[year][week] = 0
    else:
      seenweeks[year][week] += 1

    if not day in seendays:
      seendays[day] = 1
    else:
      seendays[day] += 1

  ''' Remove weeks for which there is less than two days of results in that week. '''
  ''' Note that if we smooth the data to generate a reading every 10 minutes, there will be 144 readings per day '''
  editedweeks = dict(seenweeks)
  for year in seenweeks:
    editedweeks = dict(seenweeks[year])
    for week in seenweeks[year]:
      if seenweeks[year][week] < trim_weeks:
        del editedweeks[week]
    seenweeks[year] = dict(editedweeks)

  return (seendays, seenweeks)

def calculate_averages(data, args):
  ''' Return a dictionary with the maximum and mimimum values for each time interval

  Args:
    data: a dict with the element 'value'
    args: a dict with the elements ;

  Returns:
    g_mean: The mean of all blood glucose 'value' elements
    g_median: The median of all blood glucose 'value' elements
    a_mean: The blood glucose mean converted to an HbA1c value
    a_median: The blood glucose median converted to an HbA1c value

  Raises:
    ValueError if the blood glucose units can't be parsed or are unknown.
  '''
  g_mean   = round(np.mean([data[k].get('value', 0) for k in data]), 1)
  g_median = round(np.median([data[k].get('value', 0) for k in data]), 1)
  if args.units == UNIT_MGDL:
    a_median = (g_median + 46.7) / 28.7
    a_mean   = (g_mean   + 46.7) / 28.7
  elif args.units == UNIT_MMOLL:
    a_median = (g_median + 2.59) / 1.59
    a_mean   = (g_mean   + 2.59) / 1.59
  else:
    raise ValueError('Unknown blood glucose units for HbA1c calculations')
  return (g_mean, g_median, a_mean, a_median)


def calculate_max_min(data):
  ''' Return a dictionary with the maximum and mimimum values for each time interval

  Args:
    datas: a dict with elements 'timestamp' and 'value'

  Returns:
    intervals: a dictionary of minimum and maximum values for a a time period

  Raises:
    ValueError if an incorrectly-formatted date exists in data['timestamp']
  '''
  intervals = {}
  for d in data:
    date = d.get('date')
    date = date.replace(minute=int(date.minute/INTERVAL)*INTERVAL, second=0, microsecond=0, tzinfo=None)
    time = date.time()

    if not time in intervals:
      intervals[time] = {}
      intervals[time]['min'] = d.get('value')
      intervals[time]['max'] = d.get('value')

    if intervals[time]['min'] < d.get('value'):
      intervals[time]['min'] = d.get('value')

    if intervals[time]['max'] > d.get('value'):
      intervals[time]['max'] = d.get('value')

  return intervals

def fill_gaps(rows, interval, maxinterval=dt.timedelta(days=1)):
  ''' Fill in time gaps that may exist in a set of rows, in order to smooth drawn curves and fills

  Args:
    rows: a dict containing a 'date' entry (the result of parse_entry())
    interval: a datetime.timedelta object that defines the maximum distance allowed between two entries
    maxinterval: a datetime.timedelta object that defines the maximum amount of time, over which we ignore
      the difference between two consecutive entries

  Returns:
    filledrows: a dict containing the rows with inserted items.
  '''
  filledrows = []
  for i, row in enumerate(rows):
    filledrows.append(row)

    ''' Don't check the distance between the last value and anything! '''
    if i >= len(rows)-1:
      continue

    ''' If the next row has a time gap, create new rows to insert '''
    if rows[i+1].get('date') - rows[i].get('date') > interval and \
       rows[i+1].get('date') - rows[i].get('date') < maxinterval:

      n     = (rows[i+1].get('date') - rows[i].get('date'))//interval
      start = mdates.date2num(rows[i].get('date'))
      end   = mdates.date2num(rows[i+1].get('date'))
      lower = rows[i].get('value')
      upper = rows[i+1].get('value')

      ''' Calculate an range for each interval, assuming a straight line between the start and
          end of the gap.
          Use n+2 so we can remove the first and last value which overlap with existing values '''
      periods = np.linspace(start, end, n+2)
      periods = periods[1:n+1]
      values  = np.linspace(lower, upper, n+2)
      values  = values[1:n+1]

      for j, val in enumerate(values):
        period = mdates.num2date(periods[j])
        period = period.replace(microsecond=0, tzinfo=None)

        item = {
            'date': period,
            'meal': '',
            'value': float('%.2f' % val),
            'comment': '',
            'timestamp': period.strftime('%Y-%m-%dT%H:%M:%S'),
            'measure_method': 'Estimate',
        }
        filledrows.append(item)

  return filledrows

def verify_pagesize(pagesize = None):
  ''' Check the page size '''
  if re.search('a4', pagesize, flags=re.IGNORECASE) is not None:
    pagesize = (11.69, 8.27)
  elif re.search('letter', pagesize, flags=re.IGNORECASE) is not None:
    pagesize = (11, 8.5)
  elif re.search('\d+(cm|in),\d+/', pagesize, flags=re.IGNORECASE) is not None:
    ''' Do nothing '''
  else: # A4 size default
    pagesize = (11.69, 8.27)
  return pagesize

def verify_units(units = None, high = None, low = None):
  ''' Standardise units for output and for the A1c calculations '''
  if re.search('mg', units, flags=re.IGNORECASE) is not None:
    units = UNIT_MGDL
  elif re.search('mm', units, flags=re.IGNORECASE) is not None:
    units = UNIT_MMOLL
  elif isinstance(high, (int, float)) or isinstance(low, (int, float)):
    ''' If units are not specified by the arguments or calling function, let's assume they are
        mg/dL if the high is more than 35 or the low more than 20 '''
    if (isinstance(high, (int, float)) and (high > 35) or
        isinstance(low,  (int, float)) and (low > 20)):
      units = UNIT_MGDL
    else:
      units = UNIT_MMOLL
  else:
    ''' Leave empty so we can auto-detect based on input '''
    units = ''
  return units

def parse_arguments():
  parser = argparse.ArgumentParser(description='Convert a CSV file containing blood sugar measurements into graphs')

  parser.add_argument(
    '--input', '-i', action='store', required=True, type=str, dest='input_file',
    help='Select the CSV file exported by glucometerutils.')
  parser.add_argument(
    '--output', '-o', action='store', type=str, dest='output_file',
    help=('Select the path for the output file.'))

  parser.add_argument(
    '--pagesize', action='store', required=False, type=str, default='',
    help=('Page size of output PDF (currently, letter or A4).'))
  parser.add_argument(
    '--graphs', action='store', required=False, type=int, default=2, dest='graphs_per_page',
    help=('Number of graphs to print per page.'))
  parser.add_argument(
    '--icons', action='store_true', required=False, default=True,
    help=('Print food and injection indicators (default: true).'))
  parser.add_argument(
    '--fingerstick', action='store_true', required=False, default=True,
    help=('Include manual finger stick results (default: true).'))

  parser.add_argument(
    '--units', action='store', required=False, type=str,
    default='mmol/L', choices=(UNIT_MGDL, UNIT_MMOLL),
    help=('The measurement units used (mmol/L or mg/dL).'))
  parser.add_argument(
    '--low', action='store', required=False, type=float, default=DEFAULT_LOW,
    help=('Minimum of target glucose range.'))
  parser.add_argument(
    '--high', action='store', required=False, type=float, default=DEFAULT_HIGH,
    help=('Maximum of target glucose range.'))

  args = parser.parse_args()

  args.pagesize = verify_pagesize(args.pagesize)
  args.units = verify_units(args.units, args.high, args.low)
  if args.units == UNIT_MMOLL:
    args.graph_max = GRAPH_MAX_MMOLL
    args.graph_min = GRAPH_MIN_MMOLL
  else:
    args.graph_max = GRAPH_MAX_MGDL
    args.graph_min = GRAPH_MIN_MGDL
    ''' If the user specified the units but not the high or low targets, set them now '''
    if args.high == DEFAULT_HIGH or args.low == DEFAULT_LOW:
      args.high  = convert_glucose_unit(args.high, UNIT_MMOLL)
      args.low   = convert_glucose_unit(args.low, UNIT_MMOLL)

  ''' Ensure we have a valid number of graphs_per_page '''
  if not isinstance(args.graphs_per_page, int) or args.graphs_per_page < 1:
    args.graphs_per_page = 2

  return args

def from_csv(csv_file, newline=''):
  '''Returns the reading as a formatted comma-separated value string.'''
  data = csv.reader(csv_file, delimiter=',', quotechar='"')
  fields = [ 'timestamp', 'value', 'meal', 'measure_method', 'comment' ]
  rows = []
  for row in data:
    item = dict(zip(fields, row))
    rows.append(item)
  return rows

def convert_glucose_unit(value, from_unit, to_unit=None):
  """Convert the given value of glucose level between units.

  Args:
    value: The value of glucose in the current unit
    from_unit: The unit value is currently expressed in
    to_unit: The unit to conver the value to: the other if empty.

  Returns:
    The converted representation of the blood glucose level.

  Raises:
    exceptions.InvalidGlucoseUnit: If the parameters are incorrect.
    Note that this is defined by the main glucometerutils package, from which
    this function is duplicated, and is not a valid exception for this script.
    So let's hope it doesn't get triggered!
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


if __name__ == "__main__":
    main()

# vim: set expandtab shiftwidth=2 softtabstop=2 tw=0 :
