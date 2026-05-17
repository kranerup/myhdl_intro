from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator
import os
# Now we're going to simulate with a new simulator, Icarus Verilog.
# The builtin MyHDL sim has one limitation. The value of signals
# are purely binary, 0 or 1. In most Verilog simulators a signal can
# have more values. Particularly important is that Verilog has a
# signal value 'x'. This represents an uninitialized signal or a
# a signal that for some other reason has an unknown value.
# This is very important to ensure that a silicon circuit works
# after power up since the initial state then is undefined.


# We're going to use the Verilog file produced by ex_4_flop.
# When the first_flop.v was generated there was also a tb_first_flop.v
# created. This is a wrapper that connects the MyHDL testbench with
# the Verilog simulator.


# Here the DUT is replace with a Icarus simulator of the DUT.
def first_flop(i,o,clk):
    cosim = Cosimulation("vvp -m ../myhdl/cosimulation/icarus/myhdl.vpi dut.o -fst-speed", **locals())
    return cosim

# The testbench below is the same as in ex_4_flop only the content of the DUT is replaced.
def test_bench():

    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    cgen = clock_reset_generator( clk, sync_rstn )

    dut = first_flop( i=next_state, o=state, clk=clk )

    @instance
    def stimuli():
        next_state.next = 0
        yield clk.negedge

        for i in range(4):
            next_state.next = i
            print("next_state:%d" %(next_state))
            yield clk.negedge
            print("state:%d" %(state))

    return instances()

# Create the simulation model
os.system("iverilog -g2005-sv -o dut.o first_flop.v tb_first_flop.v")

# Run the cosimulation. MyHDL simulates the testbench and Icarus simulates the DUT.
sim = Simulation( test_bench() )
sim.run(100)

# View the waveform. Notice that Icarus produced a different trace format, FST. This is
# much more compact than the VCD format that MyHDL uses. 
# Look at the 'o' signal at time 0 and 100ns.
