from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

# This illustrates how MyHDL interface/blocks can be parameterized
# so that they can handle that some ports aren't connected. 

# If the 'i' input is None, meaning it's not connected then
# instead of doing the addition we just connect input to output.
def prep_input(op,m_in,i,clk,reset):
    if i is not None:
        @always_seq(clk.posedge,reset=reset)
        def min():
            m_in.next = op + i
    else:
        ipt = pass_through(op,m_in)

    return instances()

# Note that nr_mul is now a parameter that must be a constant.
@module
def do_mul(op,m_in,result,clk,reset,nr_mul):
    @always_seq(clk.posedge,reset=reset)
    def m():
        collect = modbv(0)[16:]
        for i in range(nr_mul):
            collect[:] += m_in[i] * op
        result.next = collect
    return instances()

@block
def calculation( op, result, clk, reset, nr_mul ):

    mul_in = [ signal(8) for _ in range(nr_mul) ]
    iinputs = []

    for i in range(nr_mul):
        # Here 'add_val' is sometimes None which is handled by the prep_input function.
        add_val = i if i >= 2 else None 
        iinputs.append( prep_input( op, mul_in[i], add_val, clk, reset ))

    imul = do_mul( op, mul_in, result, clk, reset, nr_mul )

    return instances()

def generate_verilog():
    clk   = signal()
    op    = signal(16)
    res   = signal(16)
    reset = ResetSignal(0, active=0, isasync=False)

    # Passing nr_mul as a constant parameter down to the different parts.
    # By convention we pass signals first followed by parameters.
    itop = calculation( op, res, clk, reset, nr_mul=4 )
    itop.convert()

if __name__ == "__main__":
    generate_verilog()
