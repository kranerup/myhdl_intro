from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

nr_mul = 4

# This function operates on one item.
def prep_input(op,m_in,i,clk,reset):
    @always_seq(clk.posedge,reset=reset)
    def min():
        m_in.next = op + i
    return instances()

# Here we take a list of signals as input so that we
# can perform the calculations in a loop.
def do_mul(op,m_in,result,clk,reset):
    @always_seq(clk.posedge,reset=reset)
    def m():
        collect = modbv(0)[16:]
        for i in range(nr_mul):
            collect[:] += m_in[i] * op
        result.next = collect
    return instances()

# This illustrates how to create blocks in a loop and connect
# to a signal list. Also we're using @block which is a newer
# MyHDL construct that allows the new .convert() method that
# you can see below. Unfortunately it is not compatible with
# all MyHDL features.
@block
def calculation( op, result, clk, reset ):

    # Create a list of signals so that we can operate on each item
    # in parallel.
    mul_in = [ signal(8) for _ in range(nr_mul) ]
    iinputs = []

    # Create multiple prep_input that will operate in parallel.
    # Each instance produce its result in one index in mul_in vector.
    for i in range(nr_mul):
        # Each prep_input instance must be saved in a list otherwise
        # MyHDL will not know they exist.
        iinputs.append( prep_input( op, mul_in[i], i, clk, reset ))

    # Collect all the parallel results.
    imul = do_mul( op, mul_in, result, clk, reset )

    return instances()

def generate_verilog():
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    # The new conversion method.
    itop = calculation( op, res, clk, reset )
    itop.convert()

if __name__ == "__main__":
    generate_verilog()
