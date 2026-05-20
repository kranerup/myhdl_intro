from myhdl import *
from modules.common.Common import compoundWidth, copySignal, pass_through, flop_e, multiflop
from modules.common.memory import memory


"""
Module for replacing deep pipelines with memory.

Note that with flops on the inputs or outputs to the memory
it does not work quite as you might expect if you fiddle
with the enable. 
The enable is only meant to be set low when there is no valid data in the pipe.
"""

def mempipe(idata, odata, enable, clk, rstn, depth=2, input_flops=0, output_flops=0, name=''):

    edepth = depth-input_flops-output_flops
    if edepth < 4:
        zPass = multiflop(idata, odata, clk, rstn, depth=depth, name=name+".i2o")
        return instances()

    raddr = Signal(intbv(0, min=0, max=edepth))
    waddr = Signal(intbv(0, min=0, max=edepth))
    
    @always(clk.posedge, rstn.negedge)
    def pipelogic():
      if rstn==0:
         raddr.next   = 0
         waddr.next   = edepth-1
      elif enable==1:
         if raddr==edepth-1:
            raddr.next = 0
         else:
             raddr.next = raddr+1
         waddr.next = raddr

    iMem = memory(
        idata   = idata,
        odata   = odata,
        raddr   = raddr,
        waddr   = waddr,
        renable = enable,
        wenable = enable,
        clk     = clk,
        rstn    = rstn, 
        depth   = edepth,
        input_flops = input_flops,
        output_flops = output_flops,
        name = name+".iMem"
    )
         
    return instances()
