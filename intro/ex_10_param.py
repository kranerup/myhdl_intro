from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

class Params:
    has_adder = False
    add_value = 33

from ex_9_calc import adder, multiplier

def calculation( op_1, op_2, result, clk, reset ):

    # There is a fundamental difference between code inside decorated
    # functions (@always_seq,always_comb...) and all other code.
    #
    # Inside decorated functions the code will be directly translated
    # to verilog and only python code that have a direct corresponande in
    # verilog will be allowed.
    #
    # But when outside decorated functions any Python code is allowed. You can
    # think of this code as creating, connecting and passing around hardware
    # components. Wheras inside decorated functions are the real hardware
    # components.
    #
    # Below we call the function "adder" and it returns something into "iadder".
    # The adder function doesn't perform the addition, it returns the hardware
    # for the adder, assigned to "iadder".
    add_res = copySignal(op_1)
    iadder = adder( op_1, op_2, add_res, clk, reset)

    mul_res = signal( len(op_1) * 2 )
    imul = multiplier( 12, add_res, mul_res, clk, reset )

    # We have a class Params that contains some parameters. This is a typical
    # way to create different hardware depending on parameters.
    # This if-statement selects which hardware that we will be created.
    # In the generated Verilog code only one of these will be created.
    # The if-statement will not be part of the hardware. This is like
    # compile time parameters (#ifdef) in C.
    if Params.has_adder:
        cnst = copySignal( op_1 )
        icnst = assign_const( cnst, Params.add_value )
        iadder_2 = adder( cnst, mul_res, result, clk, reset )
    else:
        # Since there is no adder we need to connect the multiplier
        # result to the 'result' output. This can NOT be done by assignment.
        # So "result = mul_res" will not work because we're now outside
        # decorated functions and connecting hardware signas requires hardware.
        # This is what 'pass_through' does.
        ipass = pass_through( mul_res, result)

    # Notice that all the hardware components that we created above
    # have been assigned to local variables. This is necessary. Without
    # these MyHDL will not work. This includes hardware signals.

    # The return here calls "instances" which takes all local variables
    # and figures out which of these are hardware an returns those.
    # Without this return there will be no hardware created
    # and figures out which of these are hardware an returns those.
    # Without this return there will be no hardware created
    return instances()

clk   = signal()
in1   = signal(8)
in2   = signal(8)
res   = signal(16)
reset = ResetSignal(0, active=0, isasync=False)

toVerilog.standard = 'systemverilog'
itop = toVerilog( calculation, in1, in2, res, clk, reset )

