# A memory with mulitple read and/or write ports
# The data needs to be flat signals
# TODO: An actual memory implementation

from myhdl import *
from modules.common.Common import copySignal, pass_through, compoundWidth, multiflop
from modules.common.memory import memory

def memory_multi_access( idata, odata, raddr, waddr, renable, wenable, clk, rstn, imask=None, consistency_data=None, depth=16, write_through=0, reset_value=0, pre_load=0, conf_load={}, input_flops=0, output_flops=0, hwc=None, mode="mem", name=''):

    # write_mask None or a tuple of widths that has to match the idata list
    
    rports = len(raddr)
    wports = len(waddr)
    width = compoundWidth(idata[0])
    
    if mode=="mem":
        assert not write_through, "ERROR! %s write_through is not supported for memory_multi_access in mem-mode" % name
    assert mode=="ff", "mem-mode is untested"
    assert imask==None, "write mask is untested"
    idatam   = copySignal(idata)
    odatam   = copySignal(odata)
    raddrm   = copySignal(raddr)
    waddrm   = copySignal(waddr)
    renablem = copySignal(renable)  
    wenablem = copySignal(wenable)  
    oflop = []
    iDaflop = multiflop(idata,   idatam, clk, rstn, depth=input_flops)  
    iRaflop = multiflop(raddr,   raddrm, clk, rstn, depth=input_flops)  
    iWaflop = multiflop(waddr,   waddrm, clk, rstn, depth=input_flops)  
    iReflop = multiflop(renable, renablem, clk, rstn, depth=input_flops)  
    iWeflop = multiflop(wenable, wenablem, clk, rstn, depth=input_flops)  
    oflop.append( multiflop(odatam, odata, clk, rstn, depth=output_flops) )
    data    = [Signal(modbv(0)[width:0]) for _ in range(depth)]

    if imask==None:
        write_mask = 0
    else:
        write_mask = ()
        for i in range(len(idata[0])):
            write_mask = write_mask + (len(idata[0][i]), )
            
    dmask = [ Signal(modbv(0)[width:]) for _ in range(wports) ]
    if write_mask:
        write_mask_enable = 1
        nr_of_masks = len(write_mask)
        assert nr_of_masks == len(idata[0]), "ERROR! %s write-mask/idata missmatch"
        wmask = [ Signal(modbv(0)[width:]) for _ in range(wports) ]
        idata_masked = [ Signal(modbv(0)[width:]) for _ in range(wports) ]
        idata_flat = [ Signal(modbv(0)[width:]) for _ in range(wports) ]
        zPassidata = pass_through(idatam, idata_flat, name=name+".zPassidata")
        
        @always_comb
        def setmask():
            for p in range(wports):
                m = modbv(0)[width:]
                d = modbv(0)[width:]
                w = intbv(0, min=0, max=width+1)
                c = intbv(0, min=0, max=width+1)
                for i in range(nr_of_masks):
                    w[:] = write_mask[i]
                    if imask[p][i]==1:
                        m[:] = m | ( ((1<<w)-1) << c )
                    else:
                        d[:] = d | ( ((1<<w)-1) << c )
                    c[:] += w
                wmask[p].next = m
                dmask[p].next = d
                idata_masked[p].next = idata_flat[p] & m
    else:
        write_mask_enable = 0
        idata_masked = idata
    if mode=="ff":
        @always(clk.posedge, rstn.negedge)
        def mem_def():
            if rstn==0:
                for i in range(depth):
                    data[i].next = reset_value
                for i in range(rports):
                    odatam[i].next = 0
            else:
                for i in range(wports):
                    if wenablem[i]==1:
                        if write_mask_enable==0:
                            data[waddrm[i]].next = idatam[i]
                        else:
                            data[waddrm[i]].next = idata_masked[i] | (data[waddrm[i]] & dmask[i])
                            
                for i in range(rports):
                    if renablem[i]==1:
                        odatam[i].next = data[raddrm[i]]
                        if write_through==1:
                            for j in range(wports):
                                if wenablem[j]==1 and waddrm[j]==raddrm[i]:
                                    if write_mask_enable==0:
                                        odatam[i].next = idatam[j]
                                    else:
                                        odatam[i].next = idata_masked[i] | (data[waddrm[i]] & dmask[i])
    else:
        @instance
        def preload_inst():
            for i in range(depth):
                data[i].next = reset_value
            yield delay(1)
            
        print("Warning! This inference pattern may not work. %s" % name)
        @always(clk.posedge) # PALINT no_rstn
        def mem_def():
            for i in range(wports):
                if wenablem[i]==1:
                    if write_mask_enable==0:
                        data[waddrm[i]].next = idatam[i]
                    else:
                        data[waddrm[i]].next = idata_masked[i] | (data[waddrm[i]] & dmask[i])
            for i in range(rports):
                odatam[i].next = data[raddrm[i]]
        
    return instances()
