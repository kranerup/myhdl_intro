from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const

def inc( out, clk, reset ):

    cnt = copySignal(out) #ocunter state
    @always_seq(clk.posedge,reset=reset)
    def do_inc():
        cnt.next = cnt + 1
        out.next = cnt

    return instances()

clk   = signal()
res   = signal(8)
reset = ResetSignal(0, active=0, isasync=False)

toVerilog.standard = 'systemverilog'
itop = toVerilog( inc, res, clk, reset )

