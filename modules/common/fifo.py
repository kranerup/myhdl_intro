from myhdl import *
import sys
from modules.common.Common import hwdir, rootdir, compoundWidth
from .fifo_imp import fifo_imp
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


"""
This is just a wrapper to pull settings from HwConf into the fifo.
"""

def fifo(idata,odata,push,pop,full,empty,level,clk,rstn,clear=0,depth=4,
         consistency_check=None,memoryMode='default',
         memory_input_flops='default', memory_output_flops='default', name=""):

    if memory_input_flops=='default':
        memory_input_flops = hwconf.memory_input_flops
    if memory_output_flops=='default':
        memory_output_flops = hwconf.memory_output_flops
        
    if memoryMode!='default':
        mode = memoryMode
    elif memory_input_flops > 0 or memory_output_flops > 0:
        mode = "mem"
        if hwconf.memory_flop_limit != None:
            if depth*compoundWidth(idata) < hwconf.memory_flop_limit:
                mode = 'ff'
    else:
        mode = 'mem'
    print("Instanciated fifo %s with memory_input_flops %s, memory_output_flops %s, mode %s" % (name, memory_input_flops, memory_output_flops, mode))
    iF = fifo_imp(idata, odata, push, pop, full, empty, level, clk, rstn, clear, depth,
                  consistency_check, memoryMode=mode, memory_input_flops=memory_input_flops, memory_output_flops=memory_output_flops, name=name+".iF")
    return instances()
