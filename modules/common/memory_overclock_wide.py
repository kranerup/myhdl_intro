from myhdl import *
from .Common import pass_through, sliceSignal, signalType, listType, copySignal, mux2, flop, compoundWidth, multiflop, slice_stable_randrange
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
Use a higher clock to make wide memories narrower.
"""

def memory_overclock_wide( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data=None, depth=16, write_through=0, reset_value=0, pre_load=0,conf_load={}, input_flops=0, output_flops=0, hwc=None, single_ported=False, wclk=None, wrstn=None, clk_fast=None, divisor=None, soft_reset=None, doing_init=None, force_latency=None, name=''):

    print("Instanciated memory_overclock_wide %s with write_through=%s, init=%s, depth=%s, divisor=%s"
          % (name, write_through, doing_init!=None, depth, divisor))

    if hwc==None:
        from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
    else:
        hwconf = hwc

    if divisor==None:
        iMem = memory( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data, depth=16, write_through=0, reset_value=0, pre_load=0, conf_load=conf_load, input_flops=input_flops, output_flops=output_flops, hwc=hwc, single_ported=single_ported, wclk=wclk, wrstn=wstrn,  name=name+".iMem")
        return instances()
    else:
        assert signalType(clk_fast), "ERROR! %s clk_fast %s type %s" % (name, clk_fast, type(clk_fast).__name__)
                
    assert signalType(idata)
    assert signalType(odata)
    assert single_ported==False, "ERROR! %s no support for single ported yet" % name
    
    # Find the width/depth of the fast memory
    dw = len(idata)
    print("%s input width %s" % (name, dw))
    memw = dw//divisor
    print("%s divisor     %s" % (name, divisor))
    print("%s memw        %s" % (name, memw))
    cd = 0
    while memw*divisor < dw:            
        print("%s but %s*%s=%s < %s" % (name, memw, divisor, memw*divisor, dw))
        memw += 1
        print("%s new memw %s" % (name, memw))
    memd = depth*divisor
    
    if signalType(doing_init):
        print("memory_overclock_wide %s in init mode" % name)        
        
        if reset_value==0:
            rval = 0
        elif reset_value==(1<<dw)-1:
            rval = (1<<memw)-1
        else:
            assert False, "ERROR! memory_wide_init supports only reset value 0 and -1, because the values need to be the same for all addresses.  reset_value %s" % reset_value    
    else:
        rval=0
            
    mem_idata = Signal(intbv(0)[memw:])
    mem_odata = copySignal(mem_idata)
    mem_raddr = Signal(intbv(0, min=0, max=memd))
    mem_waddr = copySignal(mem_raddr)
    mem_renable = Signal(intbv(0)[1:])
    mem_wenable = Signal(intbv(0)[1:])
    renable_ff = copySignal(renable)
    wenable_ff = copySignal(renable)
    collision = copySignal(renable)
    collision_ff = copySignal(renable)
    idata_ff = copySignal(idata)
    
    latch_odata = copySignal(odata, t=modbv)
    sw = memw*(divisor-1)
    shift_odata = Signal(modbv(0)[sw:0])
    shunt_odata = Signal(modbv(0)[dw:0])
    
    cnt    = Signal(intbv(0, min=0, max=divisor))
    cnt_ff = Signal(intbv(0, min=0, max=divisor))

    before = Signal(intbv(0)[1:0])
    after = Signal(intbv(0)[1:0])

    from modules.common.memory_latency import memory_latency
    core_lat = memory_latency(input_flops, output_flops, divisor, wide=1)
    print("%s latency in core domain %s" % (name, core_lat))
    if force_latency==None:
        flat=core_lat
    else:
        flat=force_latency+0
    assert core_lat<=flat
    if flat > core_lat:
        iFlopo = multiflop(shunt_odata, odata, depth=force_latency-core_lat, clk=clk, rstn=rstn, name=name+".iFlopo")
    else:
        @always_comb
        def outodata():
            odata.next = shunt_odata

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
    zFlopcnt     = multiflop(cnt,       cnt_ff,       depth=rlat-1, clk=clk_fast, rstn=rstn, name=name+".zFlopcnt")
    zFlopcoll    = multiflop(collision, collision_ff, depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFlopcoll")
    zFlopid      = multiflop(idata,     idata_ff,     depth=1 if rlat>1 else 0,   clk=clk, rstn=rstn, name=name+".zFlopid")    
    
    @always(clk_fast.posedge, rstn.negedge)
    def rego():
        if rstn==0:
            shift_odata.next = 0
            latch_odata.next = 0
        else:
            if renable_ff==1:
                if cnt_ff==1:
                    shift_odata.next = mem_odata
                elif cnt_ff>1:
                    "spyglass disable W116 -- Expected loss of MSB"
                    shift_odata.next = (shift_odata << memw) | mem_odata 
            if write_through==1:
                if collision_ff==1:
                    if cnt_ff==divisor-1:
                        latch_odata.next = idata_ff
                if collision_ff==0:
                    if renable_ff==1 and cnt_ff==0:
                        "spyglass disable W116 -- Expected loss of MSB"
                        latch_odata.next = (shift_odata << memw) | mem_odata
            else:
                if renable_ff==1 and cnt_ff==0:
                    "spyglass disable W116 -- Expected loss of MSB"
                    latch_odata.next = (shift_odata << memw) | mem_odata

    shift = copySignal(cnt)
    @always_comb
    def setshift():
        shift.next = divisor - cnt - 1

    if write_through==1:
        @always_comb
        def setcollision():
            collision.next = 0
            if renable==1 and wenable==1 and raddr==waddr:
                collision.next = 1
        
    @always_comb
    def memsigs():
        mem_wenable.next = 0
        mem_waddr.next = 0
        mem_idata.next = 0
        mem_renable.next = 0
        mem_raddr.next = 0
        shunt_odata.next = latch_odata
        if wenable==1:
            mem_wenable.next = 1
            mem_waddr.next = (waddr*divisor) + cnt
            mem_idata.next = (idata>>(shift*memw) ) & ((1<<memw)-1)
        if write_through==1:
            if renable==1 and collision==0:
                mem_renable.next = 1
                mem_raddr.next = (raddr*divisor) + cnt
        else:
            if renable==1:
                mem_renable.next = 1
                mem_raddr.next = (raddr*divisor) + cnt
            
        if renable_ff==1:
            if write_through==0:
                if cnt_ff==0:
                    "spyglass disable W116 -- Expected loss of MSB"
                    shunt_odata.next = shift_odata<<memw | mem_odata 
            else:
                if cnt_ff==0 and collision_ff==0:
                    "spyglass disable W116 -- Expected loss of MSB"
                    shunt_odata.next = shift_odata<<memw | mem_odata 
                
    # The memory
    if signalType(doing_init):
        from modules.common.memory import memory_init
        iFastmeminit = memory_init(
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
            write_through = 0, # Write through is handled outside
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
            write_through = 0, # Write through is handled outside
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
