from myhdl import *
from .Common import pass_through, sliceSignal, listOfSignalsType, signalType, listType, copySignal, mux2, flop, compoundWidth, multiflop, slice_stable_randrange
from random import randrange, seed
import sys
from unittesting.asic import *
from modules.common.Common import hwdir, rootdir
import sys
import os
sys.path.append(hwdir())
sys.path.append(os.path.join(hwdir(), "hdl"))
import shutil
from subprocess import call

"""
Use a higher clock to make several ports on the same memory.
"""

def memory_overclock_ports( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data=None, depth=16, write_through=0, reset_value=0, pre_load=0,conf_load={}, input_flops=0, output_flops=0, hwc=None, single_ported=False, wclk=None, wrstn=None, clk_fast=None, divisor=None, soft_reset=None, doing_init=None, force_latency=None, name=''):

    assert listOfSignalsType(idata)
    assert listOfSignalsType(waddr)
    assert listOfSignalsType(wenable)
    assert listOfSignalsType(odata)
    assert listOfSignalsType(raddr)
    assert listOfSignalsType(renable)
    wports = len(wenable)
    rports = len(renable)
    if write_through:
        assert wports<=1, "ERROR! memory_overclock_ports does not support write_through when wports is above 1 (%s)" % wports
    print("Instanciated memory_overclock_ports %s with write_through=%s, init=%s, depth=%s, divisor=%s, wports=%s and rports=%s" % (name, write_through, doing_init!=None, depth, divisor, wports, rports))
    
    if hwc==None:
        from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
    else:
        hwconf = hwc

    if divisor==None:
        from modules.common.memory import memory
        iMem = memory( idata[0], odata[0], raddr[0], waddr[0], renable[0], wenable[0], clk, rstn, consistency_data, depth, write_through, reset_value, pre_load, conf_load, input_flops, output_flops, hwc, single_ported, wclk, wrstn,  name=name+".iMem")
        return instances()
    else:
        assert signalType(clk_fast), "ERROR! %s clk_fast %s type %s" % (name, clk_fast, type(clk_fast).__name__)
                    
    assert wports <= divisor
    assert rports <= divisor
    ww = [ len(i) for i in idata ]
    rw = [ len(i) for i in odata ]
    assert max(rw)==min(rw)
    assert max(ww)==min(ww)
    assert single_ported==False, "ERROR! %s no support for single ported yet" % name
    assert max(rports, wports)==divisor
    
    if signalType(doing_init):
        print("memory_overclock_ports %s in init mode" % name)        
    rval=reset_value
    memw = len(idata[0])
    memd = depth
    
    mem_idata = Signal(intbv(0)[memw:])
    mem_odata = copySignal(mem_idata)
    mem_raddr = Signal(intbv(0, min=0, max=memd))
    mem_waddr = copySignal(mem_raddr)
    mem_renable = Signal(intbv(0)[1:])
    mem_wenable = Signal(intbv(0)[1:])
    renable_ff = copySignal(renable)
    wenable_ff = copySignal(wenable)
    
    latch_odata = copySignal(odata, t=modbv)
    hold_odata = copySignal(odata, t=modbv)

    odata_next = copySignal(odata, t=modbv)
    
    cnt = Signal(intbv(0, min=0, max=divisor))
    cnt_ff = Signal(intbv(0, min=0, max=divisor))

    before = Signal(intbv(0)[1:0])
    after = Signal(intbv(0)[1:0])

    # Find the positive edge on clk_slow
    from modules.common.Common import find_flank
    iFlank = find_flank(
        before = before,
        after = after,
        cnt = cnt,
        clk_slow = clk,
        clk_fast = clk_fast,
        rstn = rstn,
        divisor = divisor,
        name=name+".iFlank"
    )
    rlat = 1+input_flops+output_flops
    zFloprenable = multiflop(renable,   renable_ff,   depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFloprenable")
    zFlopwenable = multiflop(wenable,   wenable_ff,   depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFlopwenable")
    zFlopcnt     = multiflop(cnt,       cnt_ff,       depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFlopcnt")
    
    @always(clk_fast.posedge, rstn.negedge)
    def rego():
        if rstn==0:
            for i in range(rports):
                latch_odata[i].next = 0
                hold_odata[i].next = 0
        else:
            if cnt_ff<rports:
                if renable_ff[cnt_ff]==1:
                    latch_odata[cnt_ff].next = mem_odata
            if cnt_ff==rports-1:
                for i in range(rports):                    
                    if i == rports-1:
                        hold_odata[i].next = mem_odata
                    else:
                        hold_odata[i].next = latch_odata[i]
    @always_comb
    def holdData():
        for i in range(rports):
            if cnt_ff==rports-1:
                if i == divisor-1:
                    odata_next[i].next = mem_odata
                else:
                    odata_next[i].next = latch_odata[i]
            else:
                odata_next[i].next = hold_odata[i]
                
    from modules.common.memory_latency import memory_latency
    core_lat = memory_latency(input_flops, output_flops, divisor, mport=1)
    if force_latency==None:
        flat=core_lat
    else:
        flat=force_latency+0
    assert core_lat<=flat
    if flat > core_lat:
        iFlopo = multiflop(odata_next, odata, depth=force_latency-core_lat, clk=clk, rstn=rstn, name=name+".iFlopo")
    else:
        @always_comb
        def passdata():
            for i in range(rports):
                odata[i].next = odata_next[i]                
    @always_comb
    def memsigs():
        mem_wenable.next = 0
        mem_waddr.next = 0
        mem_idata.next = 0
        mem_renable.next = 0
        mem_raddr.next = 0
        if cnt < wports:
            if wenable[cnt]==1:
                mem_wenable.next = 1
                mem_waddr.next = waddr[cnt]
                mem_idata.next = idata[cnt]

        if cnt < rports:
            if renable[cnt]==1:
                mem_renable.next = 1
                mem_raddr.next = raddr[cnt]
            
    # The memory
    if signalType(doing_init):
        from modules.common.memory import memory_init
        iFastmem = memory_init(
            mem_idata,
            mem_odata,
            mem_raddr,
            mem_waddr,
            mem_renable,
            mem_wenable,
            clk=clk_fast,
            rstn=rstn,
            consistency_data=consistency_data,
            depth=memd,
            write_through = write_through,
            reset_value = rval,
            pre_load=pre_load,
            conf_load=conf_load,
            input_flops=input_flops, output_flops=output_flops,
            hwc=hwc,
            soft_reset=soft_reset,
            doing_init=doing_init,
            name=name+'.iFastmem'
        )
    else:
        from modules.common.memory import memory
        iFastmem = memory(
            mem_idata,
            mem_odata,
            mem_raddr,
            mem_waddr,
            mem_renable,
            mem_wenable,
            clk=clk_fast,
            rstn=rstn,
            consistency_data=consistency_data,
            depth=memd,
            write_through = write_through,
            reset_value = rval,
            pre_load=pre_load,
            conf_load=conf_load,
            input_flops=input_flops, output_flops=output_flops,
            hwc=hwc,
            single_ported=single_ported,
            wclk=wclk,
            wrstn=wrstn,
            name=name+'.iFastmem'
        )
    
    return instances()
