#!/usr/bin/env bash

root=$(realpath $(dirname ${BASH_SOURCE[0]}))/..
export PYTHONPATH=${root}/myhdl:${root}

python3 $* || exit 2
