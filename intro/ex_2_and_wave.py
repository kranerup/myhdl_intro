from myhdl import *
from modules.common.signal import signal

# Import the and_gate function.
from ex_1_and_gate import and_gate

# -------------------------------------------------
# A test bench that illustrates the function
# of the and_gate. There is one big difference between
# the and_gate code and this code. The and_gate code must
# follow very narrow rules in what code is allowed in order
# for conversion to Verilog hardware to work.
# However the test bench code is not constrained by that
# and basically any Python code is allowed.
def test_bench():

    a = signal()
    b = signal()
    out = signal()

    dut = and_gate(a, b, out) # Device Under Test

    @instance
    def stimuli():
        # set the inputs to the circuit
        a.next = 0
        b.next = 0
        yield delay(1) # let time pass, 1ns
        print("IN: %d%d | OUT: %d" % (a, b, out))
        a.next = 1
        yield delay(1)
        print("IN: %d%d | OUT: %d" % (a, b, out))
        a.next = 0
        b.next = 1
        yield delay(1)
        print("IN: %d%d | OUT: %d" % (a, b, out))
        a.next = 1
        yield delay(1)
        print("IN: %d%d | OUT: %d" % (a, b, out))

    return instances()

if __name__ == "__main__":
    # MyHDL has a builtin simulator. We can simulate the
    # circuit and the testbench and observer the behavior.
    # There are two ways to observe circuit behavior. Either
    # by print's in the code or by waveforms.
    # Waveforms are recordings of all events in the circuit
    # where signal changes value.
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench )  # turn on the waveform dumping with this
    sim = Simulation(wave_tb)
    sim.run(10) # run the simulation for 10ns

