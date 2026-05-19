from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const

# This is a counter state machine starting at 0
# at reset and then continuosly counting up.
# There is a single output which is the counter value.
# MyHDL does not allow to 
def inc( out, clk, reset ):

    #cnt = copySignal(out) #ocunter state
    #@always_seq(clk.posedge,reset=reset)
    #def do_inc():
    #    cnt.next = cnt + 1
    #    out.next = cnt

    #cnt = copySignal(out) #ocunter state
    @always_seq(clk.posedge,reset=reset)
    def do_inc():
        #cnt.next = cnt + 1
        out.next = out + 1

    return instances()

clk   = signal()
res   = signal(8)
reset = ResetSignal(0, active=0, isasync=False)

toVerilog.standard = 'systemverilog'
itop = toVerilog( inc, res, clk, reset )

