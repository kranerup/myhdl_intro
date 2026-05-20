from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

# Examples of Verilog functions, inline MyHDL functions
# and Verilog modules.

# This decorator will make MyHDL create a Verilog module.
# When do_mul is used in the calculation function below it
# will become an instantiation of this module. The name
# of the file and the Verilog module is pa_<func-name>_<hash>
# This is to create unique/conflict-free names.
@module
def do_mul(op,result,clk,reset,nr_mul):

    # This will be a Verilog 'function' which is limited
    # to having a single return value of type integer.
    # And integer in Verilog is 32 bits signed. This makes
    # it harder to use functions.
    def normal_function( a, b ):
        tmp = a + 33
        return a + b + tmp

    # Inline decorator makes function that can be called in
    # always blocks. They do not have a return value so
    # they can not be called inside expressions.
    @inline
    def assignable( res, a, b ):
        tmp = modbv(0)[10:]
        tmp[:] = a << 2 
        res.next = a + b + 123 + tmp # it is allowed to assign to signals

    @always_seq(clk.posedge,reset=reset)
    def mul():
        collect = modbv(0)[16:]
        for i in range(nr_mul):
            collect[:] = normal_function( collect, op )
        assignable( result, collect, op )
        #result.next = collect

    return instances()

def calculation( op, result, clk, reset, nr_mul ):

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
