from myhdl import *
from .Common import pass_through, signalType, listType, modInc, copySignal
from .Common import compoundWidth, mux2, flop_e, flop, pipeline
from .memory import memory

"""
File status: 
A fifo with multiple write ports. 
Meant to be used in front of QE in multi-slice designs.
Just started.

"""

def pack(idata, ivalid_mask, odata, onr_valid, clk, rstn, name):
    # The packing will need to be pipelined
    ilen = len(idata)
    iw = len(idata[0])
    
    @always_comb
    def packit():
        tmp = [ modbv(0)[iw:] ]
        icnt = 0
        for i in range(ilen):
            odata[i].next = 0
            if ivalid_mask[i] == 1:
                odata[icnt].next = idata[i]
                icnt += 1
        onr_valid.next = icnt        
    return instances()
            
def fifo_multi_write(
        idata, odata, push, pop,
        full, empty, level, clk,
        rstn, clear=0, depth=4, consistency_check=None,
        memoryMode='mem', memory_input_flops='default', memory_output_flops='default', 
        name=""):

    wports = len(idata)
    assert len(push)==wports
    wports_w = (wports-1).bit_length()
    iw = len(idata[0])

    # First pack the incoming data so it is compact
    ipacked = copySignal[idata]
    ipushes = Signal(intbv(0, min=0, max=wports))
    opacked = copySignal[idata]
    opushes = copySignal(ipushes)
    
    iPack = pack(idata, push, ipacked, ipushes, clk, rstn, name = name + ".iPack")

    # Then push to the fifo
    # We push only the data from received in a single clock cycle
    # to a single fifo entry, thus often leaving a lot of space. TODO: Pack data more efficiently in the FIFO

    fifo_idata = Signal(intbv(0)[iw*wports+len(nr_of_pushes):])
    fifo_odata = copySignal(flat_pdata)
    zFlatten  = pass_through(ipacked+[ipushes], fifo_idata, name=name+".zFlatten")
    zExplaode = pass_through(fifo_odata, opacked+[opushes], name=name+".zFlatten")
    fifo_push = Signal(modbv(0)[1:])
    fifo_pop = Signal(modbv(0)[1:])
    current_items = copySignal(ipushes)

    @always_comb
    def setpush():
        fifo_push.next = nr_of_pushes > 0
        fifo_pop.next = current_items == 1 and pop==1


        
    @always(clk.posedge, rstn.negedge)
    def popmachine():
        if rstn == 0:
            current_items.next = 0
        else:
            if fifo_empty==1 and fifo_push==1:
                current_items.next = ipushes
            elif fifo_pop==1:
                current_items.next = opushes
            elif pop==1:
                current_items.next = current_items - 1
    
    iFifo = fifo(
        idata = flat_padata,
        odata = flat_odata,
        push = fifo_push,
        pop = fifo_pop,
        full = fifo_full,
        empty = fifo_empty,
        level = None,
        clk = clk,
        rstn = rstn,
        clear = clear,
        depth = depth,
        name = name+".fifo"
    )
    
    return instances()

