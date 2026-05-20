from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

def calculation( op, result, clk, reset ):

    @always_seq(clk.posedge,reset=reset)
    def the_calc():
        # Create local bit variables. MyHDL has both intbv and modbv
        # but modbv is preferred in most situations.
        hi = modbv(0)[8:] # 8 bit wide, initial value 0
        lo = modbv(0)[8:]
        lo[:] = op[8:] # assign to lo the value of bits 7:0 of op ([:] is necessary) 
        hi[:] = op[16:8] # bits 15:8 of op
        lo[:] = lo + 3
        hi[:] = hi ^ lo
        result.next = concat(lo,hi) # concatenate bit variables, highest bits is left most parameter

    return instances()

if __name__ == "__main__":
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( calculation, op, res, clk, reset )

