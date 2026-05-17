from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator

def first_flop(i,o,clk,reset):
    # Now we have a slightly different way to create a flipflop.
    # This is the preferred way of coding state machines and flipflops.
    # We're using always_seq and we provide a reset signal.
    # With this construct the code for reseting signals is
    # automatically created. See the Verilog file.
    @always_seq(clk.posedge,reset=reset)
    def ff():
        o.next = i
    return instances()

# -----------------------------------------------
def test_bench():

    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    cgen = clock_reset_generator( clk, sync_rstn )

    reset = ResetSignal(0, active=0, isasync=True)

    dut = first_flop( i=next_state, o=state, clk=clk, reset=reset )

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

if __name__ == "__main__":
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench ) 
    sim = Simulation(wave_tb)
    sim.run(100)


    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)
    # We're using a special signal class ResetSignal. This provides the
    # possibility to change if reset should be active on 0 or 1 and it also
    # allows synchronous and asynchronous reset. Try changing active/iasync
    # and see the change in the Verilog.
    reset = ResetSignal(0, active=0, isasync=True)

    toVerilog.standard = 'systemverilog'
    toVerilog.trace = True
    toVerilog.trace_file = "trace"
    toVerilog.trace_format = "fst"
    itop = toVerilog( first_flop, next_state, state, clk, reset )

