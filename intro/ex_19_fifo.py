from myhdl import *
from settings.hwconf import create_hwconf
create_hwconf()
from modules.common.signal import signal
from modules.common.Common import sflop, copySignal, pass_through, assign_const
from intro_common import clock_reset_generator
from modules.common.fifo import fifo

# Instantiate a fifo from the library. Always pop if not empty.
def top( din, valid_in, dout, valid_out, clk, rst ):

    do_pop = signal()
    empty = signal()
    full = signal()
    level = signal(4)

    @always_comb
    def p():
        do_pop.next = not empty

    ififo = fifo(
            idata = din,
            odata = dout,
            push = valid_in,
            pop=do_pop,
            full=full,
            empty=empty,
            level=level,
            clk=clk,
            rstn=rst,
            depth=8 )

    return instances()

def generate_verilog():
    clk   = signal()
    rst = ResetSignal(0, active=0, isasync=False)

    din = signal(8)
    dout = signal(8)
    valid_in = signal()
    valid_out = signal()

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( top, din, valid_in, dout, valid_out, clk, rst)

def test_bench():
    clk   = signal()
    rstn = ResetSignal(0, active=0, isasync=True)

    din = signal(8)
    dout = signal(8)
    valid_in = signal()
    valid_out = signal()

    cgen = clock_reset_generator( clk, rstn )
    dut = top( din, valid_in, dout, valid_out, clk, rstn )

    @instance
    def stimuli():
        din.next = 1
        valid_in.next = 0

        for i in range(10):
            yield clk.negedge
            if i % 2 == 0:
                din.next = din + 1
                valid_in.next = 1
            else:
                valid_in.next = 0

    return instances()

def sim():
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench )  # turn on the waveform dumping with this
    sim = Simulation(wave_tb)
    sim.run(200)


if __name__ == "__main__":
    generate_verilog()
    sim()
