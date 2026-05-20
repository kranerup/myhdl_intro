from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator

# A class that holds a set of signals is called an interface.
# The purpose is to simplify connection between blocks
# so that the signals only needs to be declared in one places
# and then passed as a single parameter to modules.
class APB:
    def __init__( self, dwidth, awidth ):
        self.paddr = signal(awidth)
        self.psel = signal()
        self.penable = signal()
        self.pwrite = signal()
        self.pwdata = signal(dwidth)
        self.pready = signal()
        self.prdata = signal(dwidth)
        self.pslverr = signal()

# A minimal APB slave that listens for the APB write transaction
# and if the address matches it outputs the value written.
def apb_slave(bus,out,clk,reset):

    @always_seq(clk.posedge,reset=reset)
    def reader():
        if bus.psel == 1 and bus.penable == 1 and bus.pwrite == 1:
            # apb write operation
            if bus.paddr == 0x1111:
                out.next = bus.pwdata
        bus.pready.next = 1
        
    return instances()

# Note that this example only connects a few of the APB bus signals
# and therefore the MyHDL conversion will warn of undriven signal.
def generate_verilog():
    clk   = signal()
    reset = ResetSignal(0, active=0, isasync=False)
    bus = APB(32,16)
    pio = signal(32)

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( apb_slave, bus, pio, clk, reset )

if __name__ == "__main__":
    generate_verilog()
