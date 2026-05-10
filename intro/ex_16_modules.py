from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

#@module
def do_mul(op,result,clk,reset,nr_mul):

    @inline
    def prep_input(op,i):
        return op + i

    @always_seq(clk.posedge,reset=reset)
    def mul():
        collect = modbv(0)[16:]
        for i in range(nr_mul):
            mmm = modbv(0)[16:]
            mmm[:] = prep_input(op,i)
            collect[:] += mmm * op
        result.next = collect
    return instances()

def calculation( op, result, clk, reset, nr_mul ):

    #mul_in = [ signal(8) for _ in range(nr_mul) ]
    #iinputs = []

    #for i in range(nr_mul):
    #    add_val = i
    #    iinputs.append( prep_input( op, mul_in[i], add_val, clk, reset ))

    imul = do_mul( op, result, clk, reset, nr_mul )

    return instances()

def generate_verilog():
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    #itop = calculation( op, res, clk, reset, nr_mul=4 )
    #itop.convert()

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( calculation, op, res, clk, reset, 4  )

if __name__ == "__main__":
    generate_verilog()
