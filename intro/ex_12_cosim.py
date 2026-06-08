# Runs the cosimulation of the verilog produced by ex_12_assign.
# Before running this the first time you must have Icarus
# verilog simulator installed. You must also compile the cosim
# code: cd ../myhdl/cosimulation/icarus; make

from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

def calculation( op, result, clk, reset ):
    cosim = Cosimulation("vvp -m ../myhdl/cosimulation/icarus/myhdl.vpi dut.o -fst-speed", **locals())
    return cosim

def test_bench( ):

    clk   = signal()
    op    = Signal(modbv(10)[16:])
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)
    cgen = clock_reset_generator( clk, reset )

    icalc = calculation( op, res, clk, reset)

    return instances()

import os
os.system("iverilog -g2005-sv -o dut.o calculation.v tb_calculation.v")

sim = Simulation( test_bench() )
sim.run(100)
