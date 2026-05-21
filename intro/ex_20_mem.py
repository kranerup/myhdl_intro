from myhdl import *
from modules.common.signal import signal
from intro_common import clock_reset_generator

# Memories in MyHDL/Verilog can be seen as just a
# set of flip-flops that can be selectably be written to
# and read from using an address.
#
# Memories are often described by how many ports they have.
# By ports is meant how many independent operations that can be done per clock cycle.
#
# Another aspect of memories is that they can have an access latency
# of 0 to several cycles. Especially large memories in ASIC technology
# have 1-3 cycle access latency.

# This is a memory with one read port and one write port. Each cycle
# there can be one read operation and one write operation.
# The read result has a latency of one cycle. This means that if
# you request a read with an address in one cycle then the
# resulting read data is available in the following clock cycle.

# The actual implementation of this memory might be flip-flops
# or RAMs if the technology is an FPGA. For ASIC it will be flip-flops
# but by instantiating a RAM module instead of this MyHDL code it
# could be a RAM. In the common library there is flexible memory
# module that automatically will do this.
def dp_mem(
    idata,
    odata,
    raddr,
    waddr, 
    renable,
    wenable,
    clk,
    reset,
    depth, # number of memory words/addresses
    name):

    width = len(idata)

    data = [ signal(width) for _ in range( depth ) ]

    @always_seq(clk.posedge,reset=reset)
    def ports():
        # A write port for a flip-flop memory will result in
        # a decoder that converts the address to a write signal
        # for every flip-flop.
        if wenable == 1:
            if int(waddr) > int(depth):
                print("wenable and waddr > depth",int(waddr),depth,len(waddr))
            data[ waddr ].next = idata
        # A read port for a flip-flop memory is a multiplexer 
        # to select one memory word out of all words. Note that
        # in this example if you in one cycle are reading the same address as
        # you are writing then the read data will be not be the write data.
        if renable == 1:
            odata.next = data[ raddr ]

    return instances()

def test_bench():
    clk   = signal()
    rstn = ResetSignal(0, active=0, isasync=False)

    din = signal(8)
    dout = signal(8)
    rd = signal()
    wr = signal()
    raddr = signal(4)
    waddr = signal(4)

    cgen = clock_reset_generator( clk, rstn )
    dut = dp_mem(
        idata = din,
        odata = dout,
        raddr = raddr,
        waddr = waddr, 
        renable = rd,
        wenable = wr,
        clk = clk,
        reset = rstn,
        depth = 16, # number of memory words/addresses
        name='dpmem')

    @instance
    def stimuli():
        yield clk.negedge
        din.next = 100
        waddr.next = 0
        wr.next = 1
        rd.next = 0
        yield clk.negedge

        for i in range(10):
            wr.next = 1
            din.next = 100 + i + 1
            waddr.next = i + 1
            rd.next = 1
            raddr.next = i
            if i > 0:
                print("rdata %d" % (dout))
            yield clk.negedge
            

    return instances()

def sim():
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench )
    sim = Simulation(wave_tb)
    sim.run(200)

if __name__ == "__main__":
    sim()
