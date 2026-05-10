from myhdl import (
    Simulation,
    traceSignals,
    always_comb,
    instance,
    delay,
    instances,
    toVerilog,
)
from modules.common.signal import signal

def and_gate(a, b, out):

    @always_comb
    def logic():
        out.next = a & b

    return instances()

a = signal()
b = signal()
out = signal()

toVerilog.standard = 'systemverilog'
itop = toVerilog( and_gate, a, b, out )

