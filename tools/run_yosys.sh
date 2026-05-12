#!/bin/bash

repo_root=$(git rev-parse --show-toplevel)
source $repo_root/tools/tool-config.sh

vlog_files=()
stdcells=$repo_root/tools/osu018_stdcells.lib
nand2_area=24
stdcell_constraints=$repo_root/tools/osu018_constr

vlog_lib=(
  $repo_root/modules/common/verilog_memory.v
  $repo_root/modules/common/verilog_memory_fpga.v
  $repo_root/modules/common/verilog_memory_2c.v
  $repo_root/modules/common/verilog_memory_2c_fpga.v
  $repo_root/modules/common/verilog_memory_1p.v
  $repo_root/modules/common/verilog_mempipe.v 
  $repo_root/modules/common/verilog_memory_xilinx_ecc.v
  $repo_root/modules/common/verilog_memory_nodft.v
  $repo_root/modules/common/verilog_memory_1p_nodft.v
  $repo_root/modules/common/verilog_memory_2c_nodft.v
)

synt_script=$repo_root/tools/yosys_template.ys
output_file="synt.v"
json_file="synt.json"
output_dir=$repo_root/output/yosys
td=10000

if grep -q '20.04' /etc/os-release; then
  echo "Can't run yosys on a Ubuntu 20.04 machine."
  exit 2
fi

stat_top=''
design_dir=''
report=0
top_flow=0
libdir=''
set_output_dir=0

function usage {
   cat <<__END__
usage:
For top_test flow:
  run_yosys.sh --design-name=<design>
  run_yosys.sh --report --design-name=<design>
For experiments:
  The simplest way of running partial designs/modules is:
     run_yosys.sh <single-vlog-file>
  This will create an output directory based on module/file name and run synthesis.
  Top level module is assumed to be named same as file. All submodules instantiated
  will automatically read in if they exist in the same directory as the single verilog
  file.

  run_yosys.sh [--output-dir=<rundir>] [--output-file=<synt-verilog-output-file>] <vlog-files>
  run_yosys.sh <vlog-files>
  run_yosys.sh --report --output-dir=<rundir>
  run_yosys.sh --top=<top-module> <vlog-files>
__END__
}

function create_output_dir {
  vlog_file=$1
  base=$(basename $vlog_file .v)
  if ((set_output_dir)); then
    dir=$output_dir
  else
    dir=$repo_root/output/yosys_${base}
  fi

  # move existing dir to backup
  backup_dir="${dir}.bak"

  # Find an unused backup number
  i=1
  while [[ -d "${backup_dir}${i}" ]]; do
    let i++
  done

  # Rename existing directory if it exists
  if [ -d "$dir" ]; then
    mv "$dir" "${backup_dir}${i}"
  fi

  mkdir -p $dir
  source_dir=$(dirname $vlog_file)
  cp $source_dir/*.v $dir
  for f in $dir/*.v; do
    if [[ $(basename $f) != tsw_defs.v ]]; then
      mv $f ${f%.v}.sv
    fi
  done
  output_dir=$dir
}

for opt in $* ; do
  case $opt in
    --help|-h)
      usage
      exit
      ;;
    --debug)
      debug=1
      ;;
    --target-delay=*)
      td=${opt#--target-delay=}
      ;;
    --design-name=*) # output/<design-name>
      top_flow=1
      design_name=${opt#--design-name=}
      design_dir=output/$design_name
      ;;
    --output-file=*)
      output_file=${opt#--output-file=}
      ;;
    --output-dir=*)
      set_output_dir=1
      output_dir=${opt#--output-dir=}
      ;;
    --report)
      report=1
      ;;
    --top=*)
      top_instance=${opt#--top=}
      stat_top="-top ${top_instance}"
      ;;
    *)
      vlog_files+=($opt)
      ;;
  esac
done

shopt -s nullglob
if ((top_flow)); then
  output_dir=${design_dir}/runs/test_yosys
  vlog_files=( $( \
    ls -f $design_dir/hdl/verilog*.v \
       $design_dir/hdl/tsw_*.v \
       $design_dir/hdl/TCAM*.v \
       $design_dir/hdl/pa_*.v | \
    egrep -v '^pa_tb') )
  new_paths=()
  for f in ${vlog_files[@]}; do
    rp=$(realpath $f)
    new_paths+=($rp)
  done
  vlog_files=("${new_paths[@]}")

  stat_top="-top pa_top"
  top_instance="pa_top"
  if ((report==0)); then
    if [[ -e $output_dir ]]; then
      rm -f $output_dir/*
    fi
  fi
else # module flow

  if [[ ${#vlog_files[@]} = 1 ]]; then
    # single verilog file but will read in any needed modules from the same
    # source dir
    vlog_file=${vlog_files[0]}
    create_output_dir $vlog_file
    f=$(basename $vlog_file .v)
    module_name=$f
    f=$output_dir/${f%.v}.sv
    vlog_files=($(realpath $f))

    dir=$(realpath $output_dir)
    libdir="-libdir $dir"

    # if no top module is specified we assume it's named as the verilog file
    if [[ -z $top_instance ]]; then
      stat_top="-top ${module_name}"
      top_instance=$module_name
    fi
  else
    # multiple verilog files on the command line, presumably
    # from various directories
    if [[ -z $top_instance ]]; then
      echo must specify --top instance name
      exit 2
    fi
  fi
fi

output_dir=$(realpath $output_dir)

if ((! report )); then
  
  if [[ ${#vlog_files[@]} = 0 ]]; then
    echo no verilog files on command line
    exit 2
  fi
  
  if ((debug)); then 
    set -x
  fi
  read_vlog=""
  # first read in memories and make them library/blackbox components
  for f in "${vlog_lib[@]}"; do
    read_vlog+="read_verilog -sv -lib $f\n"
  done
  for f in "${vlog_files[@]}"; do
    if [[ $f = *verilog_memory* ]]; then
      true;
    elif [[ -e $f ]]; then
      read_vlog+="read_verilog -sv $f\n"
      sed -i -E '/disable +MYHDL[0-9]+_RETURN/d' $f
    else
      echo verilog file $f doesnt exist
      exit 2
    fi
  done
  
  mkdir -p $output_dir
 
  # patch the template script with the file paths and parameters
  sed \
    -e "s|TOP_INSTANCE|${stat_top}|g" \
    -e "s|LIBDIR|${libdir}|g" \
    -e "s|TARGETDELAY|${td}|g" \
    -e "s|STDCELLLIB|${stdcells}|g" \
    -e "s|CONSTRAINTS|${stdcell_constraints}|g" \
    -e "s|OUT|$output_file|g" \
    -e "s|JSON|$json_file|g" \
    < $synt_script  | \
  awk "/READ_VERILOG/ {print \"${read_vlog}\"; next} {print}" > $output_dir/run.ys
  
  cd $output_dir
  /bin/time -f "%U %M" -o cpu-usage $YOSYS_PATH/bin/yosys run.ys > run.log
fi


if [[ $? == 0 ]]; then
  cd $output_dir
  echo "TEST OK." >> run.log

  cpu=($(cat cpu-usage))
 
  if [[ $stat_top != "" ]]; then
    # ----  hierarchical report -----
    cat <<__END__ | tee -a summary.rpt
Hierarchical report for design $design_name.
Per module count does not include multiple instances of the modules and
the gate count reported is number of gate equivalents.
__END__
    egrep 'Chip area for module' run.log | sed -e 's/.*Chip.*module //' -e 's/ *: */ /' | ( \
      while read -r line; do 
        values=($line) 
        modname=${values[0]}
        area=${values[1]}
        gates=$(python3 -c "import math; print(math.ceil($area/${nand2_area}))")
        echo $modname $gates gates
      done ) | tee -a summary.rpt

    egrep 'Chip area for top module' run.log | sed -e 's/.*Chip.*module //' -e 's/ *: */ /' | ( \
      while read -r line; do 
        values=($line) 
        modname=${values[0]}
        area=${values[1]}
        gates=$(python3 -c "import math; print(math.ceil($area/${nand2_area}))")
        echo; echo "Total area $modname $gates gate equivalents (cell area $area in 0.18um stdcell technology)"
      done ) | tee -a summary.rpt
    set -x
    $repo_root/tools/yosys-hier-report --top $top_instance --summary summary.rpt "${vlog_files[@]}" > hier_summary.rpt
    set +x
  else
    # ----  flat report -----
    tot_gates=0
    egrep 'Chip area for (top )?module' run.log | sed -e 's/.*Chip.*module //' -e 's/ *: */ /' | ( \
      while read -r line; do 
        values=($line) 
        modname=${values[0]}
        area=${values[1]}
        gates=$(python3 -c "import math; print(math.ceil($area/${nand2_area}))")
        echo $modname $gates gates
        tot_gates=$((tot_gates + gates))
      done ; echo; echo Total area $tot_gates gate equivalents ) | tee -a summary.rpt

    dffs=$(egrep '\<DFF\w+ +[0-9]+' run.log | awk '{s+=$2} END {print s}')
    echo "dff's = $dffs" | tee -a summary.rpt
  fi

  
  if ((top_flow==0)); then
    printf "\nworst delay path:\n" | tee -a summary.rpt
    grep "Extracting gate netlist of module\|ABC:.*Delay =" run.log | sed -e 's/.*Delay =\s*//' -e 's/ ps.*/ ps/' -e 's/.*of module*//' -e 's/ to .*//' | tee -a summary.rpt
    #printf "\nworst delay path:\n$delay" | tee -a summary.rpt
    printf "\n" | tee -a summary.rpt
    printf "\n" | tee -a summary.rpt
    echo output in $output_dir
  fi
  echo
  echo Yosys synthesis completed cpu-time: ${cpu[0]}s max-mem: ${cpu[1]} kbyte | tee -a summary.rpt
else
  echo Yosys synthesis FAILED >> run.log
  echo Yosys synthesis FAILED
  exit 2
fi
