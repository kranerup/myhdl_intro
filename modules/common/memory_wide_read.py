# A memory with a list of signals as output.
# The write addresses are linear, but the read address is to the
# len(odata)*width wide rows

# TODO: Use a single memory with a write mask for ASIC, and infer an asymmetric RAM for FPGA
from myhdl import *
from modules.common.Common import copySignal
from modules.common.memory import memory

def memory_wide_read( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data=None, depth=16, write_through=0, reset_value=0, pre_load=0, conf_load={}, input_flops=0, output_flops=0, hwc=None, name=''):
    

    cols = len(odata)
    rows = depth//cols
    assert cols*rows==depth, "ERROR! %s depth %s must be a multiple of the number of cols %s" % (name, depth, cols)

    iMem = []
    
    mem_waddr   = copySignal( waddr    ) 
    mem_wenable = [ copySignal( wenable  ) for _ in range(cols) ] 
    
    
    @always_comb
    def setmem():
        mem_waddr.next = waddr//cols
        for i in range(cols):
            mem_wenable[i].next = wenable==1 and (waddr%cols == i)
            
    for i in range(cols):
        iMem.append(
            memory(
                idata   = idata,
                odata   = odata[i],
                raddr   = raddr,
                waddr   = mem_waddr,
                renable = renable,
                wenable = mem_wenable[i],
                clk     = clk,
                rstn    = rstn, 
                depth   = depth, 
                consistency_data = consistency_data,
                write_through = write_through, 
                reset_value   = reset_value, 
                pre_load      = pre_load, 
                conf_load     = conf_load,
                input_flops   = input_flops,
                output_flops  = output_flops,
                hwc           = hwc,
                name=name+".iMem%s"%i
            )
        )
    return instances()
