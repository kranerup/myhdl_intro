from myhdl import *
from .Common import pass_through, sliceSignal, listOfSignalsType, signalType, listType, copySignal, mux2, flop, compoundWidth, multiflop, slice_stable_randrange, list_OR
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
Use a higher clock to merge several identical memories into one.
"""

def memory_overclock_merge( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data=None, depth=16, write_through=0, reset_value=0, pre_load=0,conf_load={}, input_flops=0, output_flops=0, hwc=None, single_ported=False, wclk=None, wrstn=None, clk_fast=None, divisor=None, soft_reset=None, doing_init=None, force_latency=None, name=''):

    if hwc==None:
        from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
    else:
        hwconf = hwc

    assert listOfSignalsType(idata)
    assert listOfSignalsType(odata)
    wports = len(idata)
    rports = len(odata)
    print("Instanciated memory_overclock_merge %s with write_through=%s, init=%s, depth=%s, divisor=%s, wports=%s and rports=%s" % (name, write_through, doing_init!=None, depth, divisor, wports, rports))

    if divisor==None:
        if force_latency!=None:
            assert force_latency==1+input_flops+output_flops 
        if doing_init:
            from modules.common.memory import memory_init
            iMem = memory_init( idata, odata, raddr, waddr, renable, wenable, clk=clk, rstn=rstn, consistency_data=consistency_data, depth=depth, write_through = write_through, reset_value = reset_value, pre_load = pre_load, conf_load = conf_load, input_flops = input_flops, output_flops = output_flops, hwc = hwc, soft_reset = soft_reset, doing_init = doing_init, name=name+'.iMem' )
        else:
            from modules.common.memory import memory
            iMem = memory( idata, odata, raddr, waddr, renable, wenable, clk, rstn, consistency_data, depth, write_through, reset_value, pre_load, conf_load, input_flops, output_flops, hwc, single_ported, wclk, wrstn,  name=name+".iMem")
        return instances()
    elif max(rports, wports)==1:
        if force_latency!=None:
            assert force_latency==1+input_flops+output_flops 
        if doing_init!=None:
            from modules.common.memory import memory_init
            iMem = memory_init( idata[0], odata[0], raddr[0], waddr[0], renable[0], wenable[0], clk=clk, rstn=rstn, consistency_data=consistency_data, depth=depth, write_through = write_through, reset_value = reset_value, pre_load = pre_load, conf_load = conf_load, input_flops = input_flops, output_flops = output_flops, hwc = hwc, soft_reset = soft_reset, doing_init = doing_init, name=name+'.iMem' )
        else:
            from modules.common.memory import memory
            iMem = memory( idata[0], odata[0], raddr[0], waddr[0], renable[0], wenable[0], clk, rstn, consistency_data, depth, write_through, reset_value, pre_load, conf_load, input_flops, output_flops, hwc, single_ported, wclk, wrstn,  name=name+".iMem")
        return instances()
    else:
        assert signalType(clk_fast), "ERROR! %s clk_fast %s type %s" % (name, clk_fast, type(clk_fast).__name__)
                    
    ww = [ len(i) for i in idata ]
    rw = [ len(i) for i in odata ]
    assert max(rw)==min(rw)
    assert max(ww)==min(ww)
    assert single_ported==False, "ERROR! %s no support for single ported yet" % name
    assert wports == rports

    max_ports = max(rports, wports)
    if max_ports > divisor:
        # Use more than one fast mem when the divisor is too small.
        dcnt = max_ports 
        mports = []
        while dcnt>0:
            if dcnt<divisor:
                mports.append(dcnt)
            else:
                mports.append(divisor)
            dcnt -= mports[-1]
        # The latencies may not match so we don't mix overclocked and non-overclocked memories
        timeout = 1000
        while min(mports) < 2 and timeout>0:
            timeout -= 1
            maxinst = 0
            for i in range(len(mports)):
                if mports[i] > mports[maxinst]:
                    maxinst = i
            try:
                oneinst = mports.index(1)
            except:
                continue
            mports[oneinst] += 1
            mports[maxinst] -= 1
                                
        mems = len(mports)
        print("%s using %s memory_overclock_merge instances because divisor %s is less than the number of ports %s. Instance ports: %s" % (
            name,
            mems,
            divisor,
            max_ports,
            mports
        ))
        iMom = []
        l = 0
        if doing_init!=None:
            mem_doing_init = [Signal(intbv(0)[1:0]) for _ in range(mems)]
            iOrinit = list_OR(mem_doing_init, doing_init, name=name+".iOrinit")
            print("%s Oring doing init %s" % (name, doing_init))
        else:
            mem_doing_init = [None for _ in range(mems)]
            print("%s Ignoring doing init %s" % (name, doing_init))
        # This craziness is due to "Signal in multiple list is not supported" preventing a straight slicing (idata[3:0])
        mem_idata   = [[ copySignal(idata[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        mem_odata   = [[ copySignal(odata[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        mem_raddr   = [[ copySignal(raddr[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        mem_waddr   = [[ copySignal(waddr[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        mem_renable = [[ copySignal(renable[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        mem_wenable = [[ copySignal(wenable[0]) for _ in range(mports[i]) ] for i in range(mems) ]
        zPassid = pass_through(idata, mem_idata, name=name+".zPassid")
        zPassod = pass_through(mem_odata, odata, name=name+".zPassdd")
        zPassra = pass_through(raddr, mem_raddr, name=name+".zPassra")
        zPasswa = pass_through(waddr, mem_waddr, name=name+".zPasswa")
        zPassre = pass_through(wenable, mem_wenable, name=name+".zPassre")
        zPasswe = pass_through(renable, mem_renable, name=name+".zPasswe")
        for i in range(mems):
            if mports[i]>1:
                iMom.append(
                    memory_overclock_merge( mem_idata[i], mem_odata[i], mem_raddr[i], mem_waddr[i], mem_renable[i], mem_wenable[i], clk, rstn, consistency_data, depth, write_through, reset_value, pre_load,conf_load, input_flops, output_flops, hwc, single_ported, wclk, wrstn, clk_fast, divisor, soft_reset, mem_doing_init[i], force_latency=force_latency, name=name+'.iMom%s'%i)
                )
            else:
                from modules.common.memory_overclock_wide import memory_overclock_wide
                print("%s Using overclock_wide for the last single instance memory" % name)
                iMom.append(
                    memory_overclock_wide( mem_idata[i][0], mem_odata[i][0], mem_raddr[i][0], mem_waddr[i][0], mem_renable[i][0], mem_wenable[i][0], clk, rstn, consistency_data, depth, write_through, reset_value, pre_load,conf_load, input_flops, output_flops, hwc, single_ported, wclk, wrstn, clk_fast, divisor, soft_reset, mem_doing_init[i], force_latency=force_latency, name=name+'.iMomwide%s'%i)
                    )

        return instances()
    
    # Find the width/depth of the fast memory
    dw = len(idata[0])
    print("%s input width %s" % (name, dw))
    memw = dw
    print("%s divisor     %s" % (name, divisor))
    mems=max(wports, rports)
    memd=depth*mems
    
    if signalType(doing_init):
        print("memory_overclock_merge %s in init mode" % name)        
    rval=reset_value
            
    mem_idata = Signal(intbv(0)[memw:])
    mem_odata = copySignal(mem_idata)
    mem_raddr = Signal(intbv(0, min=0, max=memd))
    mem_waddr = copySignal(mem_raddr)
    mem_renable = Signal(intbv(0)[1:])
    mem_wenable = Signal(intbv(0)[1:])
    renable_ff = copySignal(renable)
    renable_f2 = copySignal(renable)
    wenable_ff = copySignal(renable)
    
    latch_odata = copySignal(odata, t=modbv)
    hold_odata = copySignal(odata, t=modbv)
    odata_next = copySignal(odata, t=modbv)
    
    cnt = Signal(intbv(0, min=0, max=divisor))
    cnt_ff = Signal(intbv(0, min=0, max=divisor))
    cnt_f2 = Signal(intbv(0, min=0, max=divisor))

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
    zFloprenable = multiflop(renable,    renable_ff,   depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFloprenable")
    zFloprenabl2 = multiflop(renable_ff, renable_f2,   depth=1,      clk=clk_fast, rstn=rstn, name=name+".zFloprenabl2")
    zFlopwenable = multiflop(wenable,    wenable_ff,   depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFlopwenable")
    zFlopcntff   = multiflop(cnt,        cnt_ff,       depth=rlat,   clk=clk_fast, rstn=rstn, name=name+".zFlopcntff")
    zFlopcntf2   = multiflop(cnt_ff,     cnt_f2,       depth=1,      clk=clk_fast, rstn=rstn, name=name+".zFlopcntf2")

    if rports+rlat <= divisor:
        # In this case we need wait moving the data to the hold register until after the flank
        print(name, "rports+rlat %s+%s = %s <= divisor %s, thus the latency could be 0, but it is made 1" % (rports, rlat, rports+rlat, divisor))
        data_cycle = 0
    elif rports+rlat <= 2*divisor:
        # In this case the shift data can moved directly to the hold register when it is available
        print(name, "rports+rlat %s+%s = %s <= 2*divisor %s = %s, thus the latency is 1" % (rports, rlat, rports+rlat, divisor, 2*divisor))
        data_cycle = 1
    else:
        # Here the latency need to be increased to 2
        print(name, "rports+rlat %s+%s = %s > 2*divisor %s = %s, thus the latency is 2" % (rports, rlat, rports+rlat, divisor, 2*divisor))
        data_cycle = 2
        
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
            if data_cycle==0:
                if cnt==0:
                    for i in range(rports):                    
                        hold_odata[i].next = latch_odata[i]
            else:
                if cnt_ff==rports-1:
                    for i in range(rports):                    
                        if i == rports-1:
                            hold_odata[i].next = mem_odata
                        else:
                            hold_odata[i].next = latch_odata[i]
                
    @always_comb
    def nextData():
        for i in range(rports):
            if data_cycle==0:
                odata_next[i].next = hold_odata[i]
            else:
                if cnt_ff==rports-1:
                    if i == divisor-1:
                        odata_next[i].next = mem_odata
                    else:
                        odata_next[i].next = latch_odata[i]
                else:
                    odata_next[i].next = hold_odata[i]
                    
    from modules.common.memory_latency import memory_latency
    core_lat = memory_latency(input_flops, output_flops, divisor, merge=1)
    if force_latency==None:
        flat=core_lat
    else:
        flat=force_latency+0
    assert core_lat<=flat, "ERROR! Native latency %s, cannot force lower latency %s" % (core_lat, flat)
    if flat > core_lat:
        print(name, "%s extra output flops added due to force_latency %s > mem latency %s" % (force_latency-core_lat, force_latency, core_lat))
        iFlopo = multiflop(odata_next, odata, depth=force_latency-core_lat, clk=clk, rstn=rstn, name=name+".iFlopo")
    else:
        print(name, "no extra output flops needed. force_latency %s, mem latency %s" % (force_latency, core_lat))
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
        if cnt<wports:
            if wenable[cnt]==1:
                mem_wenable.next = 1
                mem_waddr.next = cnt*depth + waddr[cnt] # TODO: Separate address counter to get rid of the mult 
                mem_idata.next = idata[cnt]
        if cnt<rports:
            if renable[cnt]==1:
                mem_renable.next = 1
                mem_raddr.next = cnt*depth + raddr[cnt] # TODO: Separate address counter to get rid of the mult             
                        
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
