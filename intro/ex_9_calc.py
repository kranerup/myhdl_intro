from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

def adder( op_a, op_b, out, clk, reset ):

    @always_seq(clk.posedge,reset=reset)
    def the_adder():
        out.next = op_a + op_b
    return instances()

def multiplier( op_a, op_b, out, clk, reset ):

    @always_seq(clk.posedge,reset=reset)
    def the_mul():
        out.next = op_a * op_b
    return instances()

def calculation( op_1, op_2, result, clk, reset ):

    # Here we need local signals to interconnect added and multiplier.
    # By using copySignal we don't need to know thw width of the signals.
    add_res = copySignal(op_1)
    iadder = adder( op_1, op_2, add_res, clk, reset)

    # The multiplication result will require 2x the number of bits of
    # the operands.
    mul_res = signal( len(op_1) * 2 )
    # Note that passing a constant will not always be allowed. If the
    # function does operations that are only available for Signal type.
    imul = multiplier( 12, add_res, mul_res, clk, reset )

    # here we create a constant signal,
    cnst = copySignal( op_1 )
    icnst = assign_const( cnst, 33 )
    iadder_2 = adder( cnst, mul_res, result, clk, reset )

    return instances()

clk   = signal()
in1   = signal(8)
in2   = signal(8)
res   = signal(16)
reset = ResetSignal(0, active=0, isasync=False)

toVerilog.standard = 'systemverilog'
toVerilog.trace = True
toVerilog.trace_file = "trace"
toVerilog.trace_format = "fst"
itop = toVerilog( calculation, in1, in2, res, clk, reset )

