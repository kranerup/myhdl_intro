from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator

def first_flop(i,o,clk):

    # A single flipflop just delaying the input one cycle.
    @always(clk.posedge)
    def ff():
        o.next = i
    return instances()

# ----------- testbench -----------------------------
def test_bench():

    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    # Use this module to create the clock and reset signals.
    cgen = clock_reset_generator( clk, sync_rstn )

    dut = first_flop( i=next_state, o=state, clk=clk )

    # Create a short sequence of input values to the flipflop.
    @instance
    def stimuli():
        next_state.next = 0
        # Note that we use negedge to drive and read signals in the
        # testbench whereas the DUT uses posedge. This eliminates
        # the risk of race between testbench signals and DUT. It also
        # makes it clear in the waveform what the order of event is.
        yield clk.negedge

        for i in range(4):
            next_state.next = i
            print("next_state:%d" %(next_state))
            yield clk.negedge
            print("state:%d" %(state))

    return instances()

if __name__ == "__main__":
    # First run the simulation with waveform. Take a look at the
    # waveform with gtkwave and see if the output of the flipflop
    # is indeed delayed one cycle with respect to the input.
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench ) 
    sim = Simulation(wave_tb)
    sim.run(100)

    # Also generate the Verilog file. Look at the file and see
    # in what way this is different from the and gate.
    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    toVerilog.standard = 'systemverilog'
    toVerilog.trace = True
    toVerilog.trace_file = "trace"
    toVerilog.trace_format = "fst"
    itop = toVerilog( first_flop, next_state, state, clk )

