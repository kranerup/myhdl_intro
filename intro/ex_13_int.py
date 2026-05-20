from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

def calculation( op, result, clk, reset ):

    @always_seq(clk.posedge,reset=reset)
    def the_calc():
        # A local variable that is neither Signal, intbv nor modbv will be an
        # integer, In verilog "integer" is a 32 bit signed type but in
        # python/myhdlsim it's arbitrary precision. If you are not careful
        # you will end up with different behavior.
        # A normal assign (not .next or [:]) is used for integers.
        i = op + 2 # Note it's ok to mix hardware signals (op) with integers,
        i += 12
        result.next = i

    return instances()

def generate_verilog():
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( calculation, op, res, clk, reset )

if __name__ == "__main__":
    generate_verilog()
