#!/usr/bin/perl

use strict;
use warnings;
use Getopt::Long;
use IPC::Open3;
use Time::Piece;

my $error = "Usage: $0 --input <CSV file> --output <output PDF> [--max <n.n>] [--low <n.n>] [--high <n.n>]\n";
my @lines;
my %seen; 
my @data;
my $gnuplot_data;
my $total_graphs;
my $count_graphs = 0; 
my $page_number  = 0;

my $input        = "";
my $output       = "";
# set these values either in mmol/L or mg/dL (don't mix them)
my $max_glucose  = 8;
my $min_glucose  = 4;
my $graph_max    = 21;
my $days_per_page = 2;
GetOptions ("input=s"  => \$input,          # The name of the CSV file from which to read values
            "output=s" => \$output,         # The name of the PDF file to output
            "high:f"   => \$max_glucose,    # The high end of your target blood glucose level
            "low:f"    => \$min_glucose,    # The low end of your target blood glucose level
            "max:i"    => \$graph_max,      # The highest displayed glucose level on each graph
            "graphs:i" => \$days_per_page)  # The number of days printed on each page
    or die $error;

open( my $ifh, '<:encoding(UTF-8)', $input ) 
    or die "Could not open file '$input' $!";
 
while ( my $row = <$ifh> ) {
    chomp( $row );
    push @lines, $row;
}

close( $ifh )
    or warn "close failed: $!";

# Set up basic gnuplot options for reading the CSV data
push @data, qq(
set datafile separator ","
set xdata time
set timefmt "%Y-%m-%d %H:%M:%S"
#set timefmt "%H:%M:%S"

set format x "%s" timedate
set format y "%.2f" numeric 

set samples 10000
);

# Get the list of days for which to produce graphs
foreach my $row ( @lines ) {
    if ( $row =~ m#^"(\d{4}-\d{2}-\d{2})#ms ) { 
        my $day = $1; 
        $seen{$day}++; 
    }
}
$total_graphs = scalar keys %seen;

# Read each line into a $Data variable for use by gnuplot
# Then sample into a smoothed plot for each day, and store each smoothed line in a new $SmoothData$date variable
foreach my $d ( sort keys %seen ) { 
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    push @data, qq(
\$Data << EOD
"timestamp","blood glucose","meal","method","comment");
    foreach my $row (@lines) {
        if ( $row =~ s#^"($d )#"$1#ms ) {
            push @data, $row;
        }
    }
    push @data, qq(EOD);

    push @data, qq(
set table \$SmoothData$label
#plot \$Data using "timestamp":"blood glucose" 
#plot \$Data using "timestamp":"blood glucose" smooth frequency
plot \$Data using "timestamp":"blood glucose" smooth mcsplines
#plot \$Data using "timestamp":"blood glucose" smooth bezier
unset table
undefine \$Data
);
}

# Set up output options for gnuplot.
# We don't bother to do this at the start, since the CSV needs a comma separator
# and the new $SmoothData, which contains a table, needs a whitespace separator
push @data, qq(
# change separator from CSV to table
reset
set datafile separator whitespace

set terminal pdf size 29.7cm,21.0cm enhanced font 'Calibri,14' linewidth 1 
#set output '$output'
set key off
set style data lines
set xdata time
set timefmt "%H:%M:%S"

set style line 100 dt 3 lw 1 lc rgb "#202020"
set style line 101 dt 1 lw 1 lc rgb "#202020"
set linetype 110 lc rgb "red"

set format x "%H:%M" timedate
set format y "%.0f" numeric 
set yrange [0:$graph_max]
# If extended to 23:59, the x grid overlaps with the border
set xrange ["00:00":"23:58"]

set lmargin 12
set rmargin 10
set tmargin 5
set bmargin 5

set multiplot title layout $days_per_page,1 

);

# For each day, generate a graph with some fancy options
foreach my $d ( sort keys %seen ) { 
    my $label = "$1$2$3" if ( $d =~ m#(\d{4})-(\d{2})-(\d{2})# );
    my $time  = Time::Piece->strptime ( $d, "%Y-%m-%d" );
    #my $title = $time->strftime("%a %d %b %Y");
    my $title = $time->strftime("%A, %d %B %Y");

    $count_graphs++;

    push @data, qq(
set title "Daily Glucose Summary for $title" font "Calibri,18"
set xlabel "Time" offset 0,-0.25
set ylabel "Blood glucose" 
set xtics left tc rgb "#000000"
set ytics 2    tc rgb "#000000"
set grid ytics ls 100

#set arrow from graph 0,first $min_glucose to graph 1,first $min_glucose ls 6 lw 2 nohead 
#set arrow from graph 0,first $max_glucose to graph 1,first $max_glucose ls 6 lw 2 nohead
set object 1 rect from 0,first $min_glucose to graph 1,first $max_glucose fc ls 6 fs solid 0.2 back

#plot \$SmoothData$label using 1:2:( \$2 > $max_glucose || \$2 < $min_glucose ? 110 : $count_graphs ) with linespoints ls 120 lc variable 
plot \$SmoothData$label using (strftime("%H:%M:%S", \$1)):2:( \$2 > $max_glucose || \$2 < $min_glucose ? 110 : 1 ) with lines lw 3 lc variable 

undefine \$SmoothData$label

# Add an x grid
set multiplot previous
set title "  "
set xlabel " " offset 0,-0.25
set ylabel " " 
set xtics tc rgb "#ffffff00" 
set ytics tc rgb "#ffffff00"
unset grid
unset object 1
set grid xtics ls 101 back
plot 1/0
);

    if ( $count_graphs % $days_per_page == 0 && $count_graphs < $total_graphs ) {
        push @data, qq(unset multiplot);
        push @data, qq(set multiplot layout $days_per_page,1);
        $page_number++;
    }

}
push @data, qq(
unset multiplot
);

# run the data through gnuplot
$gnuplot_data = join "\n", @data;

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

#open (GNUPLOT, "|gnuplot");
#print GNUPLOT $gnuplot_data;

# vim: set expandtab shiftwidth=4 softtabstop=4 :
