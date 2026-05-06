#!/usr/bin/env bash

root=$(realpath $(dirname ${BASH_SOURCE[0]}))/..
export PYTHONPATH=${root}/myhdl:${root}

python3 $* || exit 2

gtkwave trace.vcd --script=<(echo '
  set facs {}
  for {set i 0} {$i < [gtkwave::getNumFacs]} {incr i} {
    lappend facs [gtkwave::getFacName $i]
  }
  gtkwave::addSignalsFromList $facs
')
