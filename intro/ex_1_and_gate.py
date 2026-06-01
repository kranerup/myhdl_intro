# Run this example with: ./run.sh ex_1_and_gate.py
#
# After reading through the code and running it
# then you can run synthesis to create the gate-level
# implementation.
# ../tools/run_yosys.sh and_gate.v
# See the result in ../output/yosys_and_gate/synt.v
# A schematic view of the gate level implementation can be created with:
# netlistsvg ../output/yosys_and_gate/synt.json
# loupe out.svg
# 
from myhdl import always_comb, instances, toVerilog
from modules.common.signal import signal

# -------------------------------------------------
# This is MyHDL (Python) code that creates an
# AND gate.
def and_gate(
        a, # input signal
        b, # -"-
        out # output signal
        ):

    @always_comb # Tells MyHDL that this is combinational logic (i.e. not clocked)
    def the_logic(): # Must always embed the logic in a function.
        # When assigning a signal you must always use .next.
        # Unfortunately there is no error checking so if you forget
        # .next then strange things will happen.
        out.next = a + b

    # Must always call instances() at the end of any Python function that
    # contains hardware components. It's just part of the MyHDL magic. 
    return instances() 

# Now let's create Verilog from the above function.
if __name__ == "__main__":
    # The 'and_gate' function didn't declare what 'a','b','out' were.
    # In MyHDL the signals must always be created on the highest
    # hierchical level that the signals are used.
    # In this case it's at the top. These signals will be
    # the interface to the circuit.
    # Here we create three 1-bit signals.
    a   = signal(2)
    b   = signal(2)
    out = signal(2)

    # This will run the Verilog generation. After this there
    # will be an and_gate.v file. Look at that file and compare it
    # to the MyHDL code above. Notice where the 'and_gate' and 'the_logic'
    # names are used in the Verilog file.
    toVerilog.standard = 'systemverilog'
    toVerilog.no_testbench = True
    itop = toVerilog( and_gate, a, b, out )

