from myhdl import (
    Simulation,
    Cosimulation,
    traceSignals,
    toVerilog,
    always_comb,
    always,
    instance,
    delay,
    instances
)
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator
import os

# Here the DUT is replace with a Icarus simulator of the DUT.
# The testbench is the sane only the content of the DUT is replaced.
def first_flop(i,o,clk):
    cosim = Cosimulation("vvp -m ../myhdl/cosimulation/icarus/myhdl.vpi dut.o -fst-speed", **locals())
    return cosim

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

os.system("iverilog -g2005-sv -o dut.o first_flop.v tb_first_flop.v")

sim = Simulation( test_bench() )
sim.run(100)
