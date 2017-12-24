#!/usr/bin/perl
#
# Perl script to convert CSV output from glucometer into graphs, using gnuplot.
#
# Author: Timothy Allen <tim@treehouse.org.za>
# License: MIT
#
# TODO Convert to python (see # https://www.physicsforums.com/threads/gnuplot-how-to-find-the-area-under-a-curve-integrate.382070/
# )

use strict;
use warnings;
use Getopt::Long;
use IPC::Open3;
use Time::Piece;
use Time::Seconds;
use Data::Dumper;

$Data::Dumper::Sortkeys = 1;

my $error = "Usage: $0 --input <CSV file> --output <output PDF> [--max <n.n>] [--low <n.n>] [--high <n.n>]\n";
my @filelines;
my @sortedlines;
my @data;
my @avg_data;
my $intervals;
my %seen_days;
my %seen_weeks;
my $page_size;
my $gnuplot_data;
my $total_day_graphs;
my $total_week_graphs;
my $count_graphs = 0;
my $page_number  = 0;
my $interval     = 15; # The number of minutes to average points for the area range graph

my $input        = '';
my $output       = '';
# set these values either in mmol/L or mg/dL (don't mix them)
my $max_glucose  = 8;
my $min_glucose  = 4;
my $graph_max    = 21;
my $noicons      = 0;
my $units        = '';
my $page         = 'a4';
my $graphs_per_page = 2;
GetOptions ("input=s"    => \$input,          # The name of the CSV file from which to read values
            "output=s"   => \$output,         # The name of the PDF file to output
            "high:f"     => \$max_glucose,    # The high end of your target blood glucose level
            "low:f"      => \$min_glucose,    # The low end of your target blood glucose level
            "max:i"      => \$graph_max,      # The highest displayed glucose level on each graph
            "units:s"    => \$units,          # mmol/L or mg/dL
            "pagesize:s" => \$page,           # size of page to print
            "noicons"    => \$noicons,        # include icons (yes or no)
            "graphs:i"   => \$graphs_per_page)# The number of days printed on each page
    or die $error;



# Calculate the max and min glucose values for each time interval
# Takes an array ref of lines; returns a hash of intervals by time and min/max
sub calculate_max_min {
    my %opts   = @_;
    my $lines  = $opts{lines};
    my $fmt    = $opts{format} || qq(%Y-%m-%dT%H:%M:%S);
    my %intervals;
    foreach my $row ( @{$lines} ) {
        my ( $key, $value ) = split / /, $row;
        my $date  = Time::Piece->strptime( $key, $fmt );
        my ( $hour, $minute ) = ( $date->hour, $date->min );
        my $time = sprintf( "%02d:%02d:00", $hour, int($minute/$interval)*$interval );

        # Override the current minimum values for this interval if it
        # exists; otherwise, set it
        if ( exists ( $intervals{$time}{min} ) ) {
            if ( $intervals{$time}{min} < $value ) {
                $intervals{$time}{min} = $value;
            }
        } else {
            $intervals{$time}{min} = $value;
        }
        # Override the current maximum values for this interval if it
        # exists; otherwise, set it
        if ( exists ( $intervals{$time}{max} ) ) {
            if ( $intervals{$time}{max} > $value ) {
                $intervals{$time}{max} = $value;
            }
        } else {
            $intervals{$time}{max} = $value;
        }
    }
    return \%intervals;
}



open( my $ifh, '<:encoding(UTF-8)', $input )
    or die "Could not open file '$input' $!";

while ( my $row = <$ifh> ) {
    chomp( $row );
    # Clean up the comments
    my @comments;
    for my $row_comment ( $row =~ m#,"([^"]+?)"$# ) {
        for my $comment ( split /; /, $row_comment ) {
            if ($comment =~ /(Food|Rapid-acting insulin|Long-acting insulin)(?: \((.*?)\))/ ) {
                my $type = $1;
                my $value = $2 if defined $2;
                $value =~ s#(\d+)(\.\d+)?#$1#;
                $value .= "R" if ( $type =~ /Rapid/i );
                $value .= "L" if ( $type =~ /Long/i );

                $type  =~ s#Food#{/: 🍎}#i;
                $type  =~ s#Rapid-acting insulin#{/: 💉}^{/:=10 ${value}}#i;
                $type  =~ s#Long-acting insulin#{/: 💉}^{/:=10 ${value}}#i;

                if ( grep m#\{.*?💉\}#, @comments ) {
                    map { s#^(\{.*?💉\}.*\d+\S?)(.*)$#$1/$value$2#i; } @comments;
                } else {
                    push @comments, $type;
                }
            }
        }
    }
    my $comment = join "", @comments;

    # Parse CSV into whitespace-separated tokens to avoid conflicting separators
    $row =~ s#^"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})","([\d\.]+)",.*,"(.*?)"$#$1T$2 $3 "$comment"#;

    # Remove icons if not requested
    $row =~ s# "[^"]+"## if ( $noicons );

    push @filelines, $row;
}

close( $ifh )
    or warn "close failed: $!";

if ( $page =~ /a4/i ) {
    $page_size = "29.7cm,21.0cm";
} elsif ( $page =~ /letter/i ) {
    $page_size = "11in,8.5in";
} elsif ( $page =~ /\d+(cm|in),\d+/ ) {
    $page_size = $page;
} else {
    # A4 size default
    $page_size = "29.7cm,21.0cm";
}

# Standardise units for gnuplot's A1C calculations
if ( $units =~ /mg/i ) {
    $units = 'mg/dL';
} elsif ( $units =~ /mmol/i ) {
    $units = 'mmol/L';
} else {
    $units = '';
}

# Get the list of days for which to produce graphs
foreach my $row ( @filelines ) {
    if ( $row =~ m#^((\d{4})-(\d{2})-(\d{2}))#ms ) {
        my ( $date,$year,$month,$day ) = ( $1, $2, $3, $4 );
        my $time  = Time::Piece->strptime( $date, "%Y-%m-%d" );
        my $week = $time->strftime("%W");
        $seen_weeks{$year}{$week}++;
        $seen_days{$date}++;
    }
}
# Remove weeks for which there is less than a day of results in that week
# (In a full day, assuming a reading is taken every 15 minutes, there will be 96 readings)
foreach my $year ( sort keys %seen_weeks ) {
    foreach my $week ( sort keys %{$seen_weeks{$year}} ) {
        delete $seen_weeks{$year}{$week} if ( scalar $seen_weeks{$year}{$week} < 96 );
    }
}
$total_day_graphs = scalar keys %seen_days;
$total_week_graphs = scalar keys %seen_weeks;

$intervals = calculate_max_min( 'lines' => \@filelines, 'format' => '%Y-%m-%dT%H:%M:%S' );

# Set up basic gnuplot output options
push @data, qq(
set terminal pdf size $page_size enhanced font 'Calibri,14' linewidth 1
#set output '$output'

# Set universal styles
set style fill transparent solid 1 noborder

# Set style for below-target fills
set linetype 110 lc rgb "#d71920" # red
# Set style for above-target fills
set linetype 111 lc rgb "#f1b80e" # yellow
# Set style for graph lines
set linetype 112 lc rgb "#02538f" # blue

);

# Read each line into a $Data variable for use by gnuplot
foreach my $d ( sort keys %seen_days ) {
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    push @data, qq(\$Data$label << EOD);
    @sortedlines = ();
    foreach my $row (@filelines) {
        if ( $row =~ m#^${d}T(.*)$# ) {
            push @sortedlines, qq($1);
        }
    }
    @sortedlines = map { "    $_" } @sortedlines; # indent data structure
    push @data, join "\n", sort @sortedlines;
    push @data, qq(EOD);
}

# Output data averages by hour of the day
push @data, qq(\$DataAvg << EOD);
@sortedlines = ();
foreach my $row (@filelines) {
    if ( $row =~ m#^\S+?T(\S+) (\S+)# ) {
        push @sortedlines, qq($1 $2);
    }
}
@sortedlines = map { "    $_" } @sortedlines; # indent data structure
push @data, join "\n", sort @sortedlines;
push @data, qq(EOD);

# Output the max and min glucose values for each $interval time period
push @data, qq(\$DataMaxMin << EOD);
@sortedlines = ();
foreach my $time  ( sort keys %$intervals ) {
    push @sortedlines, qq($time $intervals->{$time}->{max} $intervals->{$time}->{min});
}
@sortedlines = map { "    $_" } @sortedlines; # indent data structure
push @data, join "\n", sort @sortedlines;
push @data, qq(EOD);


# Output weekly data averages by hour of the day
foreach my $year ( sort keys %seen_weeks ) {
    foreach my $week ( sort keys %{$seen_weeks{$year}} ) {
        my $time  = Time::Piece->strptime( $year, "%Y" );
        my $mon = $time + ( ONE_WEEK * ( $week - 1 ) ) + ( ONE_DAY );
        my $sun = $time + ( ONE_WEEK * ( $week - 1 ) ) + ( ONE_DAY * 7 );
        my $label = $mon->strftime("%Y%m%d");

        # Select data from the week in question
        my @weeklines;

        foreach my $row ( @filelines ) {
                foreach my $dow ( 0 .. 6 ) {
                my $day = $mon + ( ONE_DAY * $dow );
                my $d   = $day->strftime("%Y-%m-%d");
                if ( $row =~ m#^$d#ms ) {
                    push @weeklines, $row;
                }
            }
        }

        push @data, qq(\$DataWeekAvg$label << EOD);
        @sortedlines = ();
        foreach my $row (@weeklines) {
	    if ($row =~  m#^\d{4}-\d{2}-\d{2}T(\S+) (\S+) # ) {
                push @sortedlines, qq($1 $2);
            }
        }
        my $week_intervals = calculate_max_min( 'lines' => \@sortedlines, 'format' => '%H:%M:%S' );
        @sortedlines = map { "    $_" } @sortedlines; # indent data structure
        push @data, join "\n", sort @sortedlines;
        push @data, qq(EOD);


        push @data, qq(\$DataWeekMaxMin$label << EOD);
        @sortedlines = ();
        foreach my $time  ( sort keys %{$week_intervals} ) {
            push @sortedlines, qq($time $week_intervals->{$time}->{max} $week_intervals->{$time}->{min});
        }
        @sortedlines = map { "    $_" } @sortedlines; # indent data structure
        push @data, join "\n", sort @sortedlines;
        push @data, qq(EOD);
    }
}


# Sample each day's values into a smoothed plot, and store each plot in a new table
push @data, qq(
set datafile separator whitespace

# Read the CSV time format
#set timefmt "%Y-%m-%dT%H:%M:%S"
set timefmt "%H:%M:%S"
# Store in table in seconds, as the value must be a number
set format x "%s" timedate
set format y "%.2f" numeric

);
foreach my $d ( sort keys %seen_days ) {
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    push @data, qq(
set samples 10000

set xdata
stats \$Data$label using 2
Mean$label = STATS_mean

set xdata time
set table \$SmoothData$label
plot \$Data$label using 1:2 smooth mcsplines
unset table

);
}

# Sample the average $interval values into a smoothed plot, and store in a new table
push @data, qq(
set datafile separator whitespace

# Read the CSV time format
set timefmt "%H:%M:%S"
# Store in table in seconds, as the value must be a number
set format x "%s" timedate
set format y "%.2f" numeric

set samples 10000

set xdata
stats \$DataAvg using 2
MedianTotal = STATS_median
MeanTotal   = STATS_mean

set xdata time

set table \$DataAvgTable
plot \$DataAvg using 1:2 smooth mcsplines
unset table

set table \$SmoothDataAvg
# Use bezier smoothing
plot \$DataAvg using 1:2 smooth bezier
#
## Alternate: Try a five-point average using data_feedback.dem
## This is more responsive to outlier points than the bezier, so bezier serves our purposes better
#samples(x) = \$1 > 4 ? 5 : (\$1+1)
#avg5(x) = (shift5(x), (back1+back2+back3+back4+back5)/samples(\$1))
#shift5(x) = (back5 = back4, back4 = back3, back3 = back2, back2 = back1, back1 = x)
## Initialize a running sum
#init(x) = (back1 = back2 = back3 = back4 = back5 = sum = 0)
#plot sum = init(0), \$DataAvg using 1:(avg5(\$2)) every 2 smooth mcsplines, \$DataAvg using 1:2 smooth bezier
#
unset table

# Convert DataMaxMin from CSV to table
set table \$DataMaxMinTable
plot \$DataMaxMin using 1:2:3 with table
unset table
);


# Sample the average $interval values by week into a smoothed plot, and store each in a new table
foreach my $year ( sort keys %seen_weeks ) {
    foreach my $week ( sort keys %{$seen_weeks{$year}} ) {
        my $time  = Time::Piece->strptime( "$year", "%Y" );
        my $mon = $time + ( ONE_WEEK * ( $week - 1 ) ) + ( ONE_DAY );
        my $label = $mon->strftime("%Y%m%d");
        push @data, qq(
set datafile separator whitespace

set timefmt "%H:%M:%S"
set format x "%s" timedate
set format y "%.2f" numeric
set samples 10000
set xdata
stats \$DataWeekAvg$label using 2
MedianTotal$label = STATS_mean
MeanTotal$label   = STATS_mean

set xdata time

set table \$DataWeekAvgTable$label
plot \$DataWeekAvg$label using 1:2 smooth mcsplines
unset table

set table \$SmoothDataWeekAvg$label
plot \$DataWeekAvg$label using 1:2 smooth bezier
unset table

# Convert DataWeekMaxMin from CSV to table
set table \$DataWeekMaxMinTable$label
plot \$DataWeekMaxMin$label using 1:2:3 with table
unset table
);

    }
}
















# Set up output options for gnuplot.
# We don't bother to do this at the start, since the CSV needs a comma separator
# and the new $SmoothData, which contains a table, needs a whitespace separator
push @data, qq(
# ensure separator handles tables
set datafile separator whitespace

set key off
set style data lines
set xdata time
set timefmt "%H:%M:%S"
set format x "%H:%M" timedate
set format y "%.0f" numeric
# If extended to 23:59, the x grid overlaps with the border
set xrange ["00:00":"23:58"]
set yrange [0:$graph_max]


set lmargin 12
set rmargin 10
set tmargin 5
set bmargin 5

);

# Plot and display a graph with the average glucose values for every $interval for all recorded days
push @data, qq(
# ensure separator handles tables
set datafile separator whitespace

set key off
set style data lines
set xdata time
set timefmt "%H:%M:%S"
set format x "%H:%M" timedate
set format y "%.0f" numeric
# If extended to 23:59, the x grid overlaps with the border
set xrange ["00:00":"23:58"]
set yrange [0:$graph_max]

set lmargin 12
set rmargin 10
set tmargin 5
set bmargin 5

set multiplot layout $graphs_per_page,1

# Add an x grid
set title "  "
set xlabel " " offset 0,-0.25
set ylabel " "
set xtics tc rgb "#ffffff00"
set ytics tc rgb "#ffffff00"
unset grid
set grid xtics lt 1 dt 1 lw 0.75 lc rgb "#a0a0a0" back
plot 1/0
unset grid
set multiplot previous

set title "Overall Average Daily Glucose" font "Calibri,18"
set xlabel "Time" offset 0,-0.25
set ylabel "Blood glucose"
set xtics left scale 0 tc rgb "#000000"
set ytics 2    scale 0 tc rgb "#000000"
set grid ytics lt 1 dt 3 lw 1 lc rgb "#202020" front

set object 1 rect from graph 0, first $min_glucose to graph 1,first $max_glucose back fc rgb "#0072b2" fs solid 0.2 transparent border rgb "#a8a8a8"

AVG = MedianTotal
AVG_LABEL = gprintf("Median glucose: %.2f", AVG)
set object 2 rect at graph 0.9, graph 0.9 fc ls 2 fs transparent solid 0.7 front size char strlen(AVG_LABEL), char 3
set label 2 AVG_LABEL at graph 0.9, graph 0.9 front center

A1C = 0
if (A1C == 0 && '$units' eq 'mg/dL') {
    A1C = (MedianTotal + 46.7) / 28.7
}
if (A1C == 0 && '$units' eq 'mmol/L') {
    A1C = (MedianTotal + 2.59) / 1.59
}
# mg/dL numbers tend to be higher than 35
if (A1C == 0 && MedianTotal >= 35) {
    A1C = (MedianTotal + 46.7) / 28.7
}
# mmol/L numbers tend to be lower than 35
if (A1C == 0 && MedianTotal < 35) {
    A1C = (MedianTotal + 2.59) / 1.59
}

A1C_LABEL = gprintf("Average A1c: %.1f%%", A1C)
set object 3 rect at graph 0.07, graph 0.9 fc ls 4 fs transparent solid 0.7 front size char strlen(A1C_LABEL), char 3
set label 3 A1C_LABEL at graph 0.07, graph 0.9 front center

plot \$DataMaxMinTable using (strftime("%H:%M:%S", \$1)):2:3 with filledcurves lc rgb "#979797" fs transparent solid 0.5, \$SmoothDataAvg using (strftime("%H:%M:%S", \$1)):2:( \$2 > $max_glucose || \$2 < $min_glucose ? 110 : 112 ) with lines lw 3 lc variable

unset object 1
unset object 2
unset object 3
unset label 2
unset label 3

unset multiplot
);
# End overall average plot



# Plot and display a graph with the average glucose values for every $interval for recorded days in a given week
push @data, qq(
set datafile separator whitespace

set key off
set style data lines
set xdata time
set timefmt "%H:%M:%S"
set format x "%H:%M" timedate
set format y "%.0f" numeric
# If extended to 23:59, the x grid overlaps with the border
set xrange ["00:00":"23:58"]
set yrange [0:$graph_max]

set lmargin 12
set rmargin 10
set tmargin 5
set bmargin 5

set multiplot layout $graphs_per_page,1
);

$count_graphs = 0;
foreach my $year ( reverse sort keys %seen_weeks ) {
    foreach my $week ( reverse sort keys %{$seen_weeks{$year}} ) {
        my $time  = Time::Piece->strptime( "$year", "%Y" );
        my $mon = $time + ( ONE_WEEK * ( $week - 1 ) ) + ( ONE_DAY );
        my $sun = $time + ( ONE_WEEK * ( $week - 1 ) ) + ( ONE_DAY * 7 );
        my $title = $mon->strftime("%A, %d %B %Y") . " to " . $sun->strftime("%A, %d %B %Y");
        my $label = $mon->strftime("%Y%m%d");
        $count_graphs++;
        push @data, qq(
# Add an x grid
set title "  "
set xlabel " " offset 0,-0.25
set ylabel " "
set xtics tc rgb "#ffffff00"
set ytics tc rgb "#ffffff00"
unset grid
set grid xtics lt 1 dt 1 lw 0.75 lc rgb "#a0a0a0" back
plot 1/0
unset grid
set multiplot previous

set title "Average Daily Glucose from $title" font "Calibri,18"
set xlabel "Time" offset 0,-0.25
set ylabel "Blood glucose"
set xtics left scale 0 tc rgb "#000000"
set ytics 2    scale 0 tc rgb "#000000"
set grid ytics lt 1 dt 3 lw 1 lc rgb "#202020" front

set object 1 rect from graph 0, first $min_glucose to graph 1,first $max_glucose back fc rgb "#0072b2" fs solid 0.2 transparent border rgb "#a8a8a8"

AVG = MedianTotal$label
AVG_LABEL = gprintf("Median glucose: %.2f", AVG)
set object 2 rect at graph 0.9, graph 0.9 fc ls 2 fs transparent solid 0.7 front size char strlen(AVG_LABEL), char 3
set label 2 AVG_LABEL at graph 0.9, graph 0.9 front center

A1C = 0
if (A1C == 0 && '$units' eq 'mg/dL') {
    A1C = (MedianTotal$label + 46.7) / 28.7
}
if (A1C == 0 && '$units' eq 'mmol/L') {
    A1C = (MedianTotal$label + 2.59) / 1.59
}
# mg/dL numbers tend to be higher than 35
if (A1C == 0 && MedianTotal$label >= 35) {
    A1C = (MedianTotal$label + 46.7) / 28.7
}
# mmol/L numbers tend to be lower than 35
if (A1C == 0 && MedianTotal$label < 35) {
    A1C = (MedianTotal$label + 2.59) / 1.59
}

A1C_LABEL = gprintf("Average A1c: %.1f%%", A1C)
set object 3 rect at graph 0.07, graph 0.9 fc ls 4 fs transparent solid 0.7 front size char strlen(A1C_LABEL), char 3
set label 3 A1C_LABEL at graph 0.07, graph 0.9 front center

plot \$DataWeekMaxMinTable$label using (strftime("%H:%M:%S", \$1)):2:3 with filledcurves lc rgb "#979797" fs transparent solid 0.5, \$SmoothDataWeekAvg$label using (strftime("%H:%M:%S", \$1)):2:( \$2 > $max_glucose || \$2 < $min_glucose ? 110 : 112 ) with lines lw 3 lc variable

unset object 1
unset object 2
unset object 3
unset label 2
unset label 3
);
        if ( $count_graphs % $graphs_per_page == 0 && $count_graphs <= $total_week_graphs ) {
            push @data, qq(unset multiplot);
            push @data, qq(set multiplot layout $graphs_per_page,1) unless ($count_graphs == $total_week_graphs);
            $page_number++;
        }
    }
}

push @data, qq(
set multiplot layout $graphs_per_page,1
);
$count_graphs = 0;
# For each day, generate a graph with some fancy options
foreach my $d ( reverse sort keys %seen_days ) {
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    my $time  = Time::Piece->strptime( $d, "%Y-%m-%d" );
    #my $title = $time->strftime("%a %d %b %Y");
    my $title = $time->strftime("%A, %d %B %Y");

    $count_graphs++;

    push @data, qq(
# Add an x grid
set title "  "
set xlabel " " offset 0,-0.25
set ylabel " "
set xtics tc rgb "#ffffff00"
set ytics tc rgb "#ffffff00"
unset grid
set grid xtics lt 1 dt 1 lw 0.75 lc rgb "#a0a0a0" back
plot 1/0
unset grid
set multiplot previous

set title "Daily Glucose Summary for $title" font "Calibri,18"
set xlabel "Time" offset 0,-0.25
set ylabel "Blood glucose"
set xtics left scale 0 tc rgb "#000000"
set ytics 2    scale 0 tc rgb "#000000"
set grid ytics lt 1 dt 3 lw 1 lc rgb "#202020" front

set object 1 rect from graph 0, first $min_glucose to graph 1,first $max_glucose back fc rgb "#0072b2" fs solid 0.2 transparent border rgb "#a8a8a8"

AVG = Mean$label
AVG_LABEL = gprintf("Median glucose: %.2f", AVG)
set object 2 rect at graph 0.9, graph 0.9 fc ls 2 fs transparent solid 0.7 front size char strlen(AVG_LABEL), char 3
set label 2 AVG_LABEL at graph 0.9, graph 0.9 front center

#plot \$SmoothData$label using (strftime("%H:%M:%S", \$1)):2:( \$2 > $max_glucose ? 111 : ( \$2 < $min_glucose ? 110 : 1 ) ) with lines lw 3 lc variable , \$Data$label using 1:($graph_max-6):3 with labels font "Calibri,18" enhanced

plot \$SmoothData$label using (strftime("%H:%M:%S", \$1)):2:( $max_glucose ) with filledcurves above lc 111 fs solid 1.0, \$SmoothData$label using (strftime("%H:%M:%S", \$1)):2:( $min_glucose ) with filledcurves below lc 110 fs solid 1.0, \$SmoothData$label using (strftime("%H:%M:%S", \$1)):2 with lines lw 3 lc 112, \$Data$label using 1:($graph_max-6):3 with labels font "Calibri,18" enhanced

unset object 1
unset object 2
unset object 3
unset label 2
unset label 3
);

    if ( $count_graphs % $graphs_per_page == 0 && $count_graphs <= $total_day_graphs ) {
        push @data, qq(unset multiplot);
        push @data, qq(set multiplot layout $graphs_per_page,1) unless ($count_graphs == $total_day_graphs);
        $page_number++;
    }

}
# End daily graph plot

push @data, qq(
unset multiplot
#test
);

# Cleanup stored variables
foreach my $d ( sort keys %seen_days ) {
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    push @data, qq(undefine \$Data$label);
    push @data, qq(undefine \$SmoothData$label);
}

push @data, qq(
undefine \$DataAvg
undefine \$DataAvgTable
undefine \$SmoothDataAvg
undefine \$DataMaxMin
undefine \$DataMaxMinTable
);


# run the data through gnuplot
$gnuplot_data = join "\n", @data;
print $gnuplot_data;

open( my $ofh, '>', $output )
    or die "Could not open file '$output' $!";

my ( $pid, $stdin, $stdout, $stderr );
use Symbol 'gensym';
$stderr = gensym;

$pid = open3( $stdin, $stdout, $stderr, 'gnuplot' );

print $stdin $gnuplot_data;
close( $stdin );

while ( <$stdout> ) {
    print $ofh "$_";
}

while ( <$stderr> ) {
    warn $_;
}

close($stdout);
close($stderr);

waitpid( $pid, 0 );
my $child_exit_status = $? >> 8;

close( $ofh )
    or warn "close failed: $!";

#open(GNUPLOT, "|gnuplot");
#print GNUPLOT $gnuplot_data;
#close(GNUPLOT);

# vim: set expandtab shiftwidth=4 softtabstop=4 tw=0 :
