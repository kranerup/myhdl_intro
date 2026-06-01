# This creates the verilog output but doesn't
# run the simulation. Run this first then run ex_12_cosim.py for simulation.
from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

def calculation( op, result, clk, reset ):

    tmp = copySignal(op)
    @always_seq(clk.posedge,reset=reset)
    def the_calc():
        # Look at this code sequence. tmp is incremented twice
        # so every time this is run it will increment op with two?
        # But if you look at the waveform it starts at 0 and increments by one.
        # This is because of 'non-blocking' assignment.
        # The .next assignments will become '<=" assignments in Verilog.
        # These assignments doesn't take effect until next time the code
        # block runs, i.e. the next clock cycle. So until then the 'tmp'
        # signals will hold the current value
        tmp.next = op
        tmp.next = tmp + 1
        tmp.next = tmp + 1
        result.next = tmp

    return instances()

def generate_verilog():
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    toVerilog.standard = 'systemverilog'
    toVerilog.trace = True
    toVerilog.trace_file = "trace"
    toVerilog.trace_format = "fst"
    itop = toVerilog( calculation, op, res, clk, reset )

if __name__ == "__main__":
    generate_verilog()
