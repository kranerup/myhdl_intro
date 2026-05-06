from myhdl import Simulation, always_comb, instance, delay, instances
from modules.common.signal import signal

def and_gate(a, b, out):

    @always_comb
    def logic():
        out.next = a & b

    return instances()

def test_bench():

    a = signal()
    b = signal()
    out = signal()

    dut = and_gate(a, b, out)

    @instance
    def stimuli():
        a.next = 0
        b.next = 0
        yield delay(1)
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

sim = Simulation(test_bench())
sim.run(10)

