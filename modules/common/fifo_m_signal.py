from myhdl import *
from .Common import pass_through, signalType, listType, modInc, compoundWidth, flop, slice2matrix, listOfSignalsType, mux_list, pipeline, copySignal
from modules.common.free import free, free_LIFO, free_flop
from .memory import *

def fifo_m_signal(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check, clk_mult=None, divisor=None, depth=4, heads=1, two_and_up=None, memory_input_flops=0, memory_output_flops=0, name=""):

    nr_of_queues = len(empty)

    visible_heads = heads
    if not visible_heads:
        print("odata", odata, type(odata).__name__)
        assert signalType(odata), "ERROR! When visible_heads==0 the odata should be a signal. %s" % name
    
    w = len(idata)
    mem_depth = depth
    assert mem_depth>nr_of_queues

    print("Instantiated fifo_m_signal %s with depth=%d, nr_of_queues=%d"%(name, depth, nr_of_queues))

    #print "FIFOm", name, "queues   ", nr_of_queues
    #print "FIFOm", name, "width    ", w
    #print "FIFOm", name, "depth    ", depth
    #print "FIFOm", name, "mem_depth", mem_depth
    #print "FIFOm", name, "odata    ", type(odata).__name__, len(odata), odata

    head    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]
    tail    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]
    
    mem_in  = copySignal(idata)
    mem_out = copySignal(idata)
    mem_ra  = copySignal(head[0])
    mem_wa  = copySignal(head[0])
    mem_re  = Signal(intbv(0)[1:0])
    mem_we  = Signal(intbv(0)[1:0])

    link_in  = copySignal(head[0])
    link_out = copySignal(head[0])
    link_ra  = copySignal(head[0])
    link_wa  = copySignal(head[0])
    link_re  = Signal(intbv(0)[1:0])
    link_we  = Signal(intbv(0)[1:0])

    out_reg = copySignal(odata)

    level_is_one       = Signal(intbv(0)[nr_of_queues:])
    level_is_two       = Signal(intbv(0)[nr_of_queues:])
    level_is_three     = Signal(intbv(0)[nr_of_queues:])
    level_two_and_up   = Signal(intbv(0)[nr_of_queues:])
    level_three_and_up = Signal(intbv(0)[nr_of_queues:])
    
    if two_and_up!=None:
        zTwo_and_up = pass_through(level_two_and_up, two_and_up, name=name+".zTwoandup")
        
    free_out = copySignal(head[0])
    num_free = copySignal(tot_level)

    zflop = []
    mem_re_d1 = copySignal(mem_re)
    mem_ra_d1 = copySignal(mem_ra)
    mem_we_d1 = copySignal(mem_we)
    mem_wa_d1 = copySignal(mem_wa)
    link_re_d1 = copySignal(link_re)
    link_ra_d1 = copySignal(link_ra)
    pop_enable_d1 = copySignal(pop_enable)
    pop_sel_d1 = copySignal(pop_sel)

    zflop.append(flop(mem_re, mem_re_d1, clk, rstn))
    zflop.append(flop(mem_ra, mem_ra_d1, clk, rstn))
    zflop.append(flop(mem_we, mem_we_d1, clk, rstn))
    zflop.append(flop(mem_wa, mem_wa_d1, clk, rstn))
    zflop.append(flop(link_re, link_re_d1, clk, rstn))
    zflop.append(flop(link_ra, link_ra_d1, clk, rstn))
    zflop.append(flop(pop_enable, pop_enable_d1, clk, rstn))
    zflop.append(flop(pop_sel, pop_sel_d1, clk, rstn))
    
    if clk_mult==None or divisor==1:
        assert memory_input_flops+memory_output_flops==0
        iMem  = memory(mem_in, mem_out, mem_ra, mem_wa, mem_re, mem_we, clk, rstn, depth=mem_depth, name=name+".imem")
    else:
        from .memory_overclock_wide import memory_overclock_wide
        from .memory_latency import memory_latency
        lat = memory_latency(0, 0, divisor, wide=1)
        assert lat==1, "ERROR! %s memory_overclock_wide latency %s, fifo_m_signal only works with latency 1. " % (name, lat)
        iMem  = memory_overclock_wide(
            idata = mem_in,
            odata = mem_out,
            raddr = mem_ra,
            waddr = mem_wa,
            renable = mem_re,
            wenable = mem_we,
            clk_fast = clk_mult,
            divisor = divisor,
            clk = clk,
            rstn = rstn,
            depth = mem_depth,
            input_flops  = memory_input_flops,
            output_flops = memory_output_flops,
            force_latency = 1,
            name = name+".iMem")
    ilink = memory(link_in, link_out, link_ra, link_wa, link_re, link_we, clk, rstn, depth=mem_depth, write_through=1, name=name+".ilink")
        
    # Note that the fifo_m_signal is written with the assumption that free will be able to return
    # an address as long as there are less than depth number of used addresses, but that this is not
    # true for fifo_mem3, which can have as much as eight addresses milling around in its plumbing.
    # Thus fifo_m_signal cannot be used together with free_mem3.
    # /Per
    print("Warning! fifo_m_signal %s cannot use the free_matrix_mem3, thus the free_LIFO is forced here." % name)
    ifree = free_LIFO(
        idata    = mem_ra_d1,
        odata    = free_out,
        push     = mem_re_d1,
        pop      = mem_we,
        num_free = num_free,
        clk      = clk,
        rstn     = rstn,
        consistency_check = consistency_check,
        depth    = mem_depth,
        name     = name+".free") 

    if visible_heads:
        # The out_regs
        @always(clk.posedge, rstn.negedge)
        def oreg():
            if rstn==0:
                for i in range(nr_of_queues):
                    out_reg[i].next = 0
            else:
                for i in range(len(out_reg)):
                    if empty[i]==1:
                        out_reg[i].next = 0
                if pop_sel_d1 < nr_of_queues:
                    if mem_re_d1==1:
                        out_reg[pop_sel_d1].next = mem_out
                if push_sel < nr_of_queues:
                    if push_enable==1:
                        if empty[push_sel]==1:
                            out_reg[push_sel].next = idata
                    if push_enable==1 and pop_enable==1:
                        if push_sel==pop_sel:
                            if level_is_one[push_sel]==1:
                                out_reg[push_sel].next = idata

###

    tlw = len(tot_level)
    if visible_heads:
        @always(clk.posedge, rstn.negedge)
        def headtailv():
            if rstn==0:
                for i in range(nr_of_queues):
                    tail[i].next  = 0
                    head[i].next  = 0
            else:
                if push_sel < nr_of_queues:
                    if push_enable==1:
                        if level_is_one[push_sel]==1:
                            head[push_sel].next = free_out
                        if empty[push_sel]==0:
                            tail[push_sel].next = free_out
                if pop_sel_d1 < nr_of_queues:
                    if link_re_d1==1:
                        head[pop_sel_d1].next = link_out
    else:
        @always(clk.posedge, rstn.negedge)
        def headtail():
            if rstn==0:
                for i in range(nr_of_queues):
                    tail[i].next  = 0
                    head[i].next  = 0
            else:
                if push_sel < nr_of_queues:
                    if push_enable==1:
                        if empty[push_sel]==1:
                            head[push_sel].next = free_out
                        tail[push_sel].next = free_out
                if pop_sel_d1 < nr_of_queues:
                    if link_re_d1==1:
                        head[pop_sel_d1].next = link_out
        
                    
    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            tot_level.next = 0
            full.next = 0
            empty.next = (1<<nr_of_queues) - 1
            level_is_one.next = 0
            level_is_two.next = 0
            level_is_three.next = 0
            level_two_and_up.next = 0
            level_three_and_up.next = 0
            for i in range(nr_of_queues):
                level[i].next = 0
        else:
            temp_level = modbv(0)[tlw:]
            level_inc = modbv(0)[tlw:]
            level_dec = modbv(0)[tlw:]
            full_if_push = modbv(0)[1:]
            only_push    = modbv(0)[1:]
            only_pop     = modbv(0)[1:]

            level_inc[:] = tot_level + 1
            level_dec[:] = tot_level - 1

            full_if_push[:] = level_inc >= depth

            if not (push_enable==1 and pop_enable==1 and push_sel==pop_sel):
                if push_enable==1 and push_sel < nr_of_queues:
                    empty.next[push_sel] = 0
                    if empty[push_sel]==1:
                        level_is_one.next[push_sel] = 1
                    if level_is_one[push_sel]==1:
                        level_is_one.next[push_sel] = 0
                        level_is_two.next[push_sel] = 1
                        level_two_and_up.next[push_sel] = 1
                    if level_is_two[push_sel]==1:
                        level_is_two.next[push_sel] = 0
                        level_is_three.next[push_sel] = 1
                        level_three_and_up.next[push_sel] = 1
                    if level_is_three[push_sel]==1:
                        level_is_three.next[push_sel] = 0

                    "synthesis translate_off"
                    if full==1:
                        print("ERROR pushing to full FIFO %s queue %d" % (name, push_sel))
                        assert False
                    "synthesis translate_on"
                    level[push_sel].next = level[push_sel] + 1
                if pop_enable==1 and pop_sel < nr_of_queues:
                    if level_is_one[pop_sel]==1:
                        empty.next[pop_sel] = 1
                        level_is_one.next[pop_sel] = 0
                    if level_is_two[pop_sel]==1:
                        level_is_one.next[pop_sel] = 1
                        level_is_two.next[pop_sel] = 0
                        level_two_and_up.next[pop_sel] = 0
                    if level_is_three[pop_sel]==1:
                        level_is_two.next[pop_sel] = 1
                        level_is_three.next[pop_sel] = 0
                        level_three_and_up.next[pop_sel] = 0
                    if level[pop_sel]==4:
                        level_is_three.next[pop_sel] = 1
                    "synthesis translate_off"
                    if empty[pop_sel]==1:
                        print("ERROR popping empty FIFO %s queue %d" % (name, pop_sel))
                        assert False
                    "synthesis translate_on"
                    level[pop_sel].next = level[pop_sel] - 1

                if push_enable==1 and pop_enable==0:
                    only_push[:] = 1
                elif push_enable==0 and pop_enable==1:
                    only_pop[:] = 1
                    
            if only_push:
                temp_level[:] = level_inc
            elif only_pop:
                temp_level[:] = level_dec
            else:
                temp_level[:] = tot_level
            tot_level.next = temp_level
            if ( num_free==0 or (num_free==1 and mem_we==1) or
                 ( full==1 and only_pop==0 ) or
                 ( only_push==1 and full_if_push==1 )):
                full.next = 1
            else:
                full.next = 0

    # Memory push
    if visible_heads:
        @always_comb
        def mempushv():
            mem_in.next = idata
            mem_we.next = 0
            mem_wa.next = free_out
            if push_enable==1 and push_sel<nr_of_queues:
                if empty[push_sel]==0:
                    if not (pop_enable==1 and push_sel==pop_sel and level_is_one[push_sel]==1):
                        mem_we.next = 1
    else:
        @always_comb
        def mempush():
            mem_in.next = idata
            mem_wa.next = free_out
            if push_enable==1:
                mem_we.next = 1
            else:
                mem_we.next = 0
        
    if visible_heads:
        @always_comb
        def readingv():
            mem_ra.next = 0
            mem_re.next = 0
            if pop_enable==1 and pop_sel<nr_of_queues:
                if level_two_and_up[pop_sel]==1:
                    mem_ra.next = head[pop_sel]
                    if link_re_d1==1 and pop_sel_d1==pop_sel:
                        mem_ra.next = link_out
                    mem_re.next = 1
    else:
        @always_comb
        def reading():
            mem_ra.next = 0
            if pop_enable==1 and pop_sel<nr_of_queues:
                mem_ra.next = head[pop_sel]
                if link_re_d1==1 and pop_sel_d1==pop_sel:
                    mem_ra.next = link_out
                mem_re.next = 1
            else:
                mem_re.next = 0
        
    if visible_heads:
        @always_comb
        def unlinking():
            link_re.next = 0
            link_ra.next = mem_ra
            if mem_re==1 and pop_sel<nr_of_queues:
                if level_three_and_up[pop_sel]==1 or (pop_enable==1 and push_enable==1 and pop_sel==push_sel):
                    link_re.next = 1
    else:
        @always_comb
        def unlinking():
            link_re.next = 0
            link_ra.next = mem_ra
            if mem_re==1 and pop_sel<nr_of_queues:
                if level_two_and_up[pop_sel]==1 or (pop_enable==1 and push_enable==1 and pop_sel==push_sel):
                    link_re.next = 1

    if visible_heads:
        @always_comb
        def linkingv():
            link_wa.next = 0
            link_we.next = 0
            link_in.next = free_out
            if mem_we==1 and push_sel<nr_of_queues:
                if level_two_and_up[push_sel]==1:
                    link_we.next = 1
                    link_wa.next = tail[push_sel]
    else:
        @always_comb
        def linking():
            link_wa.next = 0
            link_we.next = 0
            link_in.next = free_out
            if mem_we==1 and push_sel<nr_of_queues:
                if empty[push_sel]==0:
                    link_we.next = 1
                    link_wa.next = tail[push_sel]
                
    if listOfSignalsType(odata):
        @always_comb
        def driveoutexplode():
            for i in range(nr_of_queues):
                if mem_re_d1==1 and pop_sel_d1==i:
                    odata[i].next = mem_out
                else:
                    odata[i].next = out_reg[i]
    else:
        @always_comb
        def driveout():
            odata.next = mem_out

    tot_level_d1 = copySignal(tot_level)
    @always(clk.posedge, rstn.negedge)
    def assertFree():
        if rstn==0:
            tot_level_d1.next = 0
        else:
            tot_level_d1.next = tot_level
            "synthesis translate_off"
            if tot_level == 0 and tot_level_d1 == 0:
                for i in range(len(level)):
                    if level[i]!=0:
                        print("ERROR!", name, "Level counter discrepancy. tot_level =", tot_level, "level[", i, "] =", level[i])
                        assert False
                if num_free!=mem_depth:
                    print("ERROR!", name, "Level counter discrepancy. tot_level =", tot_level, "free.num_free =", num_free, "!=", mem_depth)
                    assert False
            if consistency_check==1:
                if empty==0 or tot_level!=0:
                    assert False, ("Consistency ERROR! fifo level %s != 0 for %s" % (tot_level, name))
            "synthesis translate_on"
                

    return instances()
