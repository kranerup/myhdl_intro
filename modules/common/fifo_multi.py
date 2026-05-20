from myhdl import *
from .Common import pass_through, signalType, listType, modInc, compoundWidth, compoundLen, flop, slice2matrix, listOfSignalsType, mux_list, pipeline, copySignal
from modules.common.free import free, free_LIFO, free_flop
from modules.common.fifo_m_signal import fifo_m_signal
from .memory import *
"""
File status: I think the FIFO-multi is fine (it is several fifos
stored in a single memory). 

It should not need to be able to perform any of the esoteric feats
that we expect the generic FIFO to do.
"""

def fifo_multi(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check,depth=4,input_flop=0,output_flop=0,push_latency=0, pop_latency=0,mode="default",heads=1, two_and_up=None, name=""):
    """
    A bank of fifos stored in a shared memory. 
    Only two fifos can be accessed any one clock cycle: One for pushing and one for popping

    """

    print("Instantiated fifo_multi %s with depth=%d, input_flop=%d, output_flop=%d, push_latency=%s, and pop_latency=%s"%(name, depth, input_flop, output_flop, push_latency, pop_latency))

    debug_in_list = [push_enable, push_sel, full, tot_level, idata]
    debug_in = Signal(intbv(0)[compoundWidth(debug_in_list):0], debug_level=1)
    zPassdbgin = pass_through(debug_in_list, debug_in, name=name+".zPassdbgin")
    
    debug_out_list = [pop_enable, pop_sel, empty, level]
    print(name, "debug_out_list", compoundLen(debug_out_list))
    debug_out = Signal(intbv(0)[compoundWidth(debug_out_list):0], debug_level=1)
    zPassdbgout = pass_through(debug_out_list, debug_out, name=name+".zPassdbgout")

    # qe needs to use lists for empty, so support both
    if listType(empty):
        elen = len(empty)
        empty_signal = Signal(intbv(0)[elen:])
        @always_comb
        def passem():
            for i in range(elen):
                empty[i].next = empty_signal[i]
    else:
        empty_signal = empty        
    
    zpass = []
    iflat = idata
    if listType(idata):
        iflat = Signal(intbv(0)[compoundWidth(idata):])
        for _ in idata:
            pass
            #print "   ", len(_)
        #print "fm flat", compoundWidth(idata)
        #print "fm iflat", type(iflat).__name__, len(iflat), iflat
        zpass.append(pass_through(idata, iflat, name=name+".fifo_flatten_in"))

        
    if heads==1:
        if listOfSignalsType(odata):
            oflat = copySignal(odata)
            zpass.append(pass_through(oflat, odata, name=name+".fifo_flatten_in"))
        else:
            oflatflat = Signal(intbv(0)[compoundWidth(odata):])
            oflat = []
            for i in range(len(odata)):
                if listType(odata[i]):
                    oflat.append(Signal(intbv(0)[compoundWidth(odata[i]):]))
                else:
                    oflat.append(copySignal(odata[i]))
            zoflat = pass_through(oflat, oflatflat, name=name+".flatflat")
            # zexp = slice2matrix(oflatflat, odata, name=name+".explode")
            zexp = pass_through(oflatflat, odata, name=name+".explode")
    else:
        assert mode=='default', "%s Only default mode supported with heads=0" % name
        assert input_flop==0, "%s Only input_flop==0 supported with heads=0" % name
        assert output_flop==0, "%s Only output_flop==0 supported with heads=0" % name
        assert push_latency==0, "%s Only push_latency==0 supported with heads=0" % name
        assert pop_latency==0, "%s Only pop_latency==0 supported with heads=0" % name
        oflat = Signal(intbv(0)[compoundWidth(odata):])
        zpass.append(pass_through(oflat, odata, name=name+".fifo_flatten_in"))

#    if len(empty_signal)==1:
#        from fifo import fifo
#        singlefifo= fifo(iflat,oflat,push_enable,pop_enable,full,empty_signal,level[0],clk,rstn,depth,name=name+".singlefifo")
#        return instances()
#

    if mode=="link":
        from .fifo_m_link import fifo_m_link
        iLink = fifo_m_link(iflat, oflat, push_enable, push_sel, pop_enable, pop_sel, full, empty_signal, level, tot_level, clk, rstn, consistency_check, depth, output_flops=output_flop, input_flops=input_flop, two_and_up=two_and_up, name=name+".iLink")
    elif push_latency>0 or pop_latency>0:
        iLatency = fifo_m_latency(iflat, oflat, push_enable, push_sel, pop_enable, pop_sel, full, empty_signal, level, tot_level, clk, rstn, consistency_check, depth, push_latency, pop_latency, name=name+".iLatency")
    elif input_flop:
        assert False, "ERROR! The input-flop fifo_multi is untested and should not be used."
        iInflop = fifo_m_timing(iflat, oflat, push_enable, push_sel, pop_enable, pop_sel, full, empty_signal, level, tot_level, clk, rstn, consistency_check, depth, output_flop=output_flop, name=name+".iInflop")
    elif output_flop:
        assert False, "ERROR! The output-flop fifo_multi is untested and should not be used."
        iOutflop = fifo_m_outflop(iflat, oflat, push_enable, push_sel, pop_enable, pop_sel, full, empty_signal, level, tot_level, clk, rstn, consistency_check, depth, name=name+".iOutflop")
    else:
        signal = fifo_m_signal(iflat, oflat, push_enable, push_sel, pop_enable, pop_sel, full, empty_signal, level, tot_level, clk, rstn, consistency_check, depth=depth, heads=heads, two_and_up=two_and_up, name=name+".iSignal")

    # trace_queue0_level = copySignal(level[0])
    # @always_comb
    # def traceverilog():
    #     trace_queue0_level.next = level[0]
    
    return instances()


def fifo_m_timing(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check, depth=4, output_flop=0, name=""):
    """
    A fifo multi where the inputs to the memories are always from a flop. 
    If output_flop=1 the outputs are also always from a flop.

    The cost for each is one flop per queue and output bit.
    """

    nr_of_queues = len(empty)
    w = len(tot_level)

    reg   = copySignal(odata)
    val   = [ Signal(intbv(0)[1:]) for _ in range(nr_of_queues) ]
    fifo_idata        = copySignal( idata       )       
    fifo_idata_n      = copySignal( idata       )       
    idata_d1          = copySignal( idata       )       
    fifo_odata        = copySignal( odata       )
    fifo_push_enable  = copySignal( push_enable )
    fifo_push_sel     = copySignal( push_sel    )
    push_enable_d1    = copySignal( push_enable )
    push_sel_d1       = copySignal( push_sel    )
    fifo_pop_enable   = copySignal( pop_enable  )
    fifo_pop_sel      = copySignal( pop_sel     )
    fifo_pop_enable_n = copySignal( pop_enable  )
    fifo_pop_sel_n    = copySignal( pop_sel     )
    fifo_full         = copySignal( full        )
    fifo_empty        = copySignal( empty       )
    fifo_level        = copySignal( level       )
    fifo_tot_level    = copySignal( tot_level   )
    dec = Signal(intbv(0)[1:])
    inc = Signal(intbv(0)[1:])
    push_reg = Signal(intbv(0)[1:])
    clear_reg = Signal(intbv(0)[1:])
    
    print("Instantiated fifo_m_timing %s with depth=%d, nr_of_queues=%d"%(name, depth, nr_of_queues))

    if output_flop:
        outflop = fifo_m_outflop(fifo_idata, fifo_odata, fifo_push_enable, fifo_push_sel, fifo_pop_enable, fifo_pop_sel, fifo_full, fifo_empty, fifo_level, fifo_tot_level, clk, rstn, consistency_check, depth=depth, name=name+".outflop")
    else:
        signal = fifo_m_signal(fifo_idata, fifo_odata, fifo_push_enable, fifo_push_sel, fifo_pop_enable, fifo_pop_sel, fifo_full, fifo_empty, fifo_level, fifo_tot_level, clk, rstn, consistency_check, depth=depth, name=name+".signal")
    
    iflop = []
    iflop.append(
        flop(idata, idata_d1, clk, rstn))
    iflop.append(
        flop(push_enable, push_enable_d1, clk, rstn))
    iflop.append(
        flop(push_sel, push_sel_d1, clk, rstn))
    
    level_is_one        = Signal(intbv(0)[nr_of_queues:])
    level_two_and_up = Signal(intbv(0)[nr_of_queues:])
    
    @always(clk.posedge, rstn.negedge)
    def reg_process():
        if rstn==0:
            fifo_pop_enable.next  = 0
            fifo_pop_sel.next     = 0
            tot_level.next        = 0
            empty.next            = (1<<nr_of_queues) - 1
            full.next             = 0
            level_is_one.next        = 0
            level_two_and_up.next = 0
            for i in range(nr_of_queues):
                reg[i].next   = 0
                val[i].next   = 0
                level[i].next = 0
        else:
            tot_level.next = tot_level + inc - dec
            full.next  = 0
            if tot_level + inc - dec >= depth-2:
                full.next = 1
            empty.next = 0
            for i in range(nr_of_queues):
                "synthesis translate_off"
                assert fifo_level[i] + val[i] == level[i] or fifo_level[i] + val[i] == level[i]+1, "ERROR! %s queue %s, %s + %s != %s (+1)" % (name, str(i), str(fifo_level[i]), str(val[i]), str(level[i]))
                "synthesis translate_on"
                if level[i] == 0:
                    empty.next[i] = 1
            fifo_pop_enable.next = fifo_pop_enable_n
            fifo_pop_sel.next    = fifo_pop_sel_n
            if dec==1:
                "synthesis translate_on"
                assert level[pop_sel]>0
                "synthesis translate_off"
                level[pop_sel].next = level[pop_sel] - 1
                if level[pop_sel] == 1:
                    empty.next[pop_sel] = 1
                    level_is_one.next[pop_sel] = 0
                if level[pop_sel] == 2:
                    level_is_one.next[pop_sel] = 1
                    level_two_and_up.next[pop_sel] = 0
            if inc==1:
                "synthesis translate_off"
                assert level[push_sel_d1]<depth-1
                "synthesis translate_on"
                level[push_sel_d1].next = level[push_sel_d1] + 1
                if level[push_sel_d1] == 0:
                    empty.next[push_sel_d1] = 0
                    level_is_one.next[push_sel_d1] = 1
                if level[push_sel_d1] == 1:
                    level_is_one.next[push_sel_d1] = 0
                    level_two_and_up.next[push_sel_d1] = 1
            for i in range(nr_of_queues):
                if clear_reg==1:
                    val[pop_sel].next = 0
                    reg[pop_sel].next = 0
                if push_reg==1:
                    "synthesis translate_off"
                    assert push_enable_d1==1
                    "synthesis translate_on"
                    val[push_sel_d1].next = 1
                    reg[push_sel_d1].next = idata_d1
                if val[i]==0 and level[i]>0:
                    if (pop_enable==0 or pop_sel!=i):
                        val[i].next   = 1
                        reg[i].next   = fifo_odata[i]

    @always_comb
    def next_process():
        inc.next = 0
        dec.next = 0
        push_reg.next = 0
        clear_reg.next = 0
        fifo_pop_enable_n.next  = 0
        fifo_push_enable.next   = 0
        fifo_pop_sel_n.next     = 0
        fifo_push_sel.next      = 0
            
        # Push
        if push_enable_d1==1 and (pop_enable==0 or push_sel_d1 != pop_sel):
#            assert tot_level<depth-1
            inc.next = 1
            if val[push_sel_d1]==1 or empty[push_sel_d1]==0:
                fifo_push_enable.next     = 1
                fifo_push_sel.next        = push_sel_d1
                fifo_idata.next           = idata_d1
            else:
                push_reg.next = 1
        # Pop
        if pop_enable==1 and (push_enable_d1==0 or push_sel_d1 != pop_sel):
#            assert tot_level>0
#            assert level[pop_sel]>0, "ERROR: %s pop when level[%s] = %s" % (name, str(pop_sel), str(level[pop_sel]))
            dec.next = 1
            if val[pop_sel]==1:
                clear_reg.next = 1
            if level_two_and_up[pop_sel]==1:
                fifo_pop_enable_n.next  = 1
                fifo_pop_sel_n.next     = pop_sel
        # Push and Pop
        if pop_enable==1 and push_enable_d1==1 and push_sel_d1 == pop_sel:
            if level_two_and_up[push_sel_d1]==1 or val[push_sel_d1]==0:
                fifo_pop_enable_n.next  = 1
                fifo_pop_sel_n.next     = pop_sel
            if val[push_sel_d1]==0:
                fifo_push_enable.next     = 1
                fifo_push_sel.next        = push_sel_d1
                fifo_idata.next           = idata_d1 
            else:
                if level_is_one[push_sel_d1]==1:
                    push_reg.next = 1
                elif level_two_and_up[push_sel_d1]==1:
                    clear_reg.next = 1
                    fifo_push_enable.next     = 1
                    fifo_push_sel.next        = push_sel_d1
                    fifo_idata.next           = idata_d1 


    mux_out = mux_list(fifo_odata, reg, odata, val, name="mux_out")

    return instances()

def fifo_m_outflop(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check, depth=4, name=""):
    """
    A fifo_multi where the output data is always from a flop. No other optimizations.
    """

    nr_of_queues = len(empty)
    w = len(tot_level)

    fifo_idata        = copySignal( idata       )       
    fifo_odata        = copySignal( odata       )
    fifo_push_enable  = copySignal( push_enable )
    fifo_push_sel     = copySignal( push_sel    )
    fifo_pop_enable   = copySignal( pop_enable  )
    fifo_pop_sel      = copySignal( pop_sel     )
    fifo_full         = copySignal( full        )
    fifo_empty        = copySignal( empty       )
    fifo_level        = copySignal( level       )
    fifo_tot_level    = copySignal( tot_level   )
    dec = Signal(intbv(0)[1:])
    inc = Signal(intbv(0)[1:])
    push_reg = Signal(intbv(0)[1:])
    feed_reg = Signal(intbv(0)[1:])
    clear_reg = Signal(intbv(0)[1:])
    
    level_is_one        = Signal(intbv(0)[nr_of_queues:])
    level_two_and_up = Signal(intbv(0)[nr_of_queues:])
    
    signal = fifo_m_signal(fifo_idata, fifo_odata, fifo_push_enable, fifo_push_sel, fifo_pop_enable, fifo_pop_sel, fifo_full, fifo_empty, fifo_level, fifo_tot_level, clk, rstn, consistency_check, depth=depth, name=name+".signal")
    
    print("Instantiated fifo_m_outflop %s with depth=%d, nr_of_queues=%d"%(name, depth, nr_of_queues))

    @always(clk.posedge, rstn.negedge)
    def reg_process():
        if rstn==0:
            tot_level.next        = 0
            empty.next            = (1<<nr_of_queues) - 1
            full.next             = 0
            level_is_one.next        = 0
            level_two_and_up.next = 0
            for i in range(nr_of_queues):
                odata[i].next   = 0
                level[i].next = 0
        else:
            tot_level.next = tot_level + inc - dec
            full.next  = 0
            if tot_level + inc - dec >= depth-1:
                full.next = 1
            if dec==1:
                "synthesis translate_off"
                assert level[pop_sel]>0
                "synthesis translate_on"
                level[pop_sel].next = level[pop_sel] - 1
                if level_is_one[pop_sel] == 1:
                    empty.next[pop_sel] = 1
                    level_is_one.next[pop_sel] = 0
                if level[pop_sel] == 2:
                    level_is_one.next[pop_sel] = 1
                    level_two_and_up.next[pop_sel] = 0
            if inc==1:
                "synthesis translate_off"
                assert level[push_sel]<depth-1;
                "synthesis translate_on"
                level[push_sel].next = level[push_sel] + 1
                if empty[push_sel] == 1:
                    empty.next[push_sel] = 0
                    level_is_one.next[push_sel] = 1
                if level_is_one[push_sel] == 1:
                    level_is_one.next[push_sel] = 0
                    level_two_and_up.next[push_sel] = 1
            if clear_reg==1:
                odata[pop_sel].next = 0
            if push_reg==1:
                "synthesis translate_off"
                assert push_enable==1
                "synthesis translate_on"
                odata[push_sel].next = idata
            if feed_reg==1:
                odata[pop_sel].next   = fifo_odata[pop_sel]

    @always_comb
    def next_process():
        inc.next = 0
        dec.next = 0
        push_reg.next = 0
        feed_reg.next = 0
        clear_reg.next = 0
        fifo_pop_enable.next  = 0
        fifo_push_enable.next = 0
        fifo_pop_sel.next     = 0
        fifo_push_sel.next    = 0
        fifo_idata.next       = 0
            
        # Push
        if push_enable==1 and (pop_enable==0 or push_sel != pop_sel):
            inc.next = 1
            if empty[push_sel]==0:
                fifo_push_enable.next     = 1
                fifo_push_sel.next        = push_sel
                fifo_idata.next           = idata
            else:
                push_reg.next = 1
        # Pop
        if pop_enable==1 and (push_enable==0 or push_sel != pop_sel):
            dec.next = 1
            if level_is_one[pop_sel]==1:
                clear_reg.next = 1
            if level_two_and_up[pop_sel]==1:
                feed_reg.next = 1
                fifo_pop_enable.next  = 1
                fifo_pop_sel.next     = pop_sel
                # Push and Pop
        if pop_enable==1 and push_enable==1 and push_sel == pop_sel:
            if level_is_one[push_sel]:
                push_reg.next = 1
            if level_two_and_up[push_sel]:
                feed_reg.next = 1
                fifo_pop_enable.next  = 1
                fifo_pop_sel.next     = pop_sel
                fifo_push_enable.next = 1
                fifo_push_sel.next    = push_sel
                fifo_idata.next       = idata

    return instances()

def fifo_m_latency(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check, depth=4,push_latency=0, pop_latency=1, name=""):

    assert pop_latency == 2
    assert push_latency == 2
    nr_of_queues = len(empty)
    w = len(idata)
    mem_depth = depth
        
    print("Instantiated fifo_m_latency %s with depth=%d, nr_of_queues=%d, mem_depth=%d, push_latency=%s, and pop_latency=%s"%(name, depth, nr_of_queues, mem_depth, push_latency, pop_latency))
    assert mem_depth>nr_of_queues

    mem_input_flops = 0
    mem_output_flops = 0
    if push_latency >= 1 and pop_latency >= 1:
        mem_input_flops = 1
    if pop_latency >= 3:
        mem_output_flops = 1
        
        
    #print "FIFOm", name, "queues   ", nr_of_queues
    #print "FIFOm", name, "width    ", w
    #print "FIFOm", name, "depth    ", depth
    #print "FIFOm", name, "mem_depth", mem_depth
    #print "FIFOm", name, "odata    ", type(odata).__name__, len(odata), odata

    head    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]
    tail    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]

    head_next = copySignal(head)
    tail_next = copySignal(tail)
    
    free_out = copySignal(head[0])
    num_free = copySignal(tot_level)

    pushes = [ Signal(intbv(0, min=0, max=push_latency+2)) for _ in range(nr_of_queues) ]
    pops   = [ Signal(intbv(0, min=0, max=pop_latency+2)) for _ in range(nr_of_queues) ]

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
    
    odata_next     = copySignal(odata)

    zflop = []
    mem_re_d  = [ copySignal(mem_re)  for _ in range(pop_latency+2) ] 
    mem_ra_d  = [ copySignal(mem_ra)  for _ in range(pop_latency+2) ] 
    mem_we_d  = [ copySignal(mem_we)  for _ in range(push_latency+2) ] 
    mem_wa_d  = [ copySignal(mem_wa)  for _ in range(push_latency+2) ] 
    link_re_d = [ copySignal(link_re) for _ in range(pop_latency+2) ] 
    link_ra_d = [ copySignal(link_ra) for _ in range(pop_latency+2) ] 
    zflop.append(pipeline(mem_re,  mem_re_d,  clk, rstn))
    zflop.append(pipeline(mem_ra,  mem_ra_d,  clk, rstn))
    zflop.append(pipeline(mem_we,  mem_we_d,  clk, rstn))
    zflop.append(pipeline(mem_wa,  mem_wa_d,  clk, rstn))
    zflop.append(pipeline(link_re, link_re_d, clk, rstn))
    zflop.append(pipeline(link_ra, link_ra_d, clk, rstn))

    pipe = []
    idata_d       = [ copySignal( idata      ) for _ in range(push_latency+2) ] 
    push_d        = [ copySignal( push_enable) for _ in range(push_latency+2) ]
    push_sel_d    = [ copySignal( push_sel   ) for _ in range(push_latency+2) ]
    pop_d         = [ copySignal( pop_enable ) for _ in range(pop_latency+2) ]
    pop_sel_d     = [ copySignal( pop_sel    ) for _ in range(pop_latency+2) ] 
    free_out_d    = [ copySignal( free_out   ) for _ in range(mem_input_flops+1) ] 
    pipe.append( pipeline( idata,       idata_d,    clk, rstn, name=name+".pidata") )
    pipe.append( pipeline( push_enable, push_d,     clk, rstn, name=name+".ppush") )
    pipe.append( pipeline( push_sel,    push_sel_d, clk, rstn, name=name+".ppusel") )
    pipe.append( pipeline( pop_enable,  pop_d,      clk, rstn, name=name+".ppop") )
    pipe.append( pipeline( pop_sel,     pop_sel_d,  clk, rstn, name=name+".pposel") )
    pipe.append( pipeline( free_out,    free_out_d, clk, rstn, name=name+".pfree") )

    push_oh = Signal(intbv(0)[nr_of_queues:0])
    push_oh_d = [ copySignal(push_oh) for _ in range(push_latency+2 ) ]
    pipe.append(pipeline(push_oh, push_oh_d, clk, rstn, name=name+".puh"))
    pop_oh = Signal(intbv(0)[nr_of_queues:0])
    pop_oh_d = [ copySignal(pop_oh) for _ in range(pop_latency+2 ) ]
    print("%s fifo_multi_latency push_oh=%s, pop_oh=%s"%(name, push_oh_d, pop_oh_d))
    pipe.append(pipeline(pop_oh, pop_oh_d, clk, rstn, name=name+".poh"))
    @always_comb
    def poh_comb():
        push_oh.next = 0
        pop_oh.next = 0
        if push_enable==1:
            push_oh.next[push_sel] = 1
        if pop_enable==1:
            pop_oh.next[pop_sel] = 1        

    skip0 = Signal(intbv(0, min=0, max=nr_of_queues+1))
    skip1 = copySignal(skip0)
    skip0_d = [ copySignal(skip0) for _ in range(push_latency+2) ]
    skip1_d = [ copySignal(skip1) for _ in range(push_latency+2) ]
    pipe.append(pipeline( skip0, skip0_d, clk, rstn, reset_value=nr_of_queues))
    pipe.append(pipeline( skip1, skip1_d, clk, rstn, reset_value=nr_of_queues))

    @always_comb
    def odata_comb():
        for i in range(nr_of_queues):
            odata_next[i].next = odata[i]
        if pop_d[ push_latency ]==1 :
            odata_next[ pop_sel_d[ push_latency ] ].next = 0;
        #if push_d[ push_latency ]==1 and empty[ push_sel_d[ push_latency ] ]==1:
        if push_d[ push_latency ]==1 and ( empty[ push_sel_d[ push_latency ] ]==1 or ( level[ push_sel_d[ push_latency ] ]==1 and pop_d[ push_latency ]==1 and push_sel_d[ push_latency ]==pop_sel_d[ push_latency ] )):
            odata_next[ push_sel_d[ push_latency ] ].next = idata_d[ push_latency ]
        if skip1_d[ push_latency ] < nr_of_queues:
            odata_next[ skip1_d[ push_latency ] ].next = idata_d[ push_latency+1 ]
        if mem_re_d[mem_input_flops+mem_output_flops+1]==1:
            odata_next[ pop_sel_d[ pop_latency ] ].next = mem_out

    @always(clk.posedge, rstn.negedge)
    def pushes_reg():
        if rstn==0:
            for i in range(nr_of_queues):
                pushes[i].next = 0
        else:
            for i in range(nr_of_queues):
                pushes[i].next = pushes[i] + push_oh_d[0][i] - push_oh_d[push_latency][i]
                
    @always(clk.posedge, rstn.negedge)
    def pops_reg():
        if rstn==0:
            for i in range(nr_of_queues):
                pops[i].next = 0
        else:
            for i in range(nr_of_queues):
                pops[i].next = pops[i] + pop_oh_d[0][i] - pop_oh_d[pop_latency+1][i]
                
#    @always_comb
#    def pushes_comb():
#        for j in range(nr_of_queues):
#            cnt = 0
#            for i in range(pop_latency):
#                cnt = cnt + push_oh_d[j][i]
#            pushes[j].next = cnt                    
            
    def count_level(push_oh_d, pop_oh_d, level, clk, rstn, cycle=0, name=""):
        @always(clk.posedge, rstn.negedge)
        def level_reg():
            if rstn==0:
                for i in range(nr_of_queues):
                    level[i].next = 0
            else:
                if push_oh_d[ cycle ] != pop_oh_d[ cycle ]:
                    for i in range(nr_of_queues):
                        "synopsys translate_off"
                        if level[i] + push_oh_d[cycle][i] - pop_oh_d[cycle][i] < 0:
                            print("%s ERROR! level less than 0 for fifo %s. %s + %s - %s = %s" %(name, i, level[i], push_oh_d[cycle][i], pop_oh_d[cycle][i], level[i] + push_oh_d[cycle][i] - pop_oh_d[cycle][i] ))
                            assert False
                        "synopsys translate_on"
                        level[i].next = level[i] + push_oh_d[cycle][i] - pop_oh_d[cycle][i]
        return instances()
    tlw = len(tot_level)
    @always(clk.posedge, rstn.negedge)
    def control_reg():
        if rstn==0:
            for i in range(nr_of_queues):
                level[i].next = 0
            tot_level.next = 0
            empty.next = (1<<nr_of_queues)-1
            full.next = 0
        else:
            temp_level = modbv(0)[tlw:]
            temp_level[:] = tot_level
            # TODO: one cycle earlier if latency > 0
            if not (push_d[ push_latency ]==1 and pop_d[ pop_latency ]==1 and push_sel_d[ push_latency ]==pop_sel_d[ pop_latency ]):
                if push_d[ push_latency ]==1:
                    level[ push_sel_d[ push_latency ] ].next = level[ push_sel_d[ push_latency ] ] + 1 
                    temp_level[:] = temp_level + 1
                    empty.next[ push_sel_d[ push_latency ] ] = 0
                if pop_d[ pop_latency ]==1:
                    level[ pop_sel_d[ pop_latency ] ].next = level[ pop_sel_d[ pop_latency ] ] - 1 
                    temp_level[:] = temp_level - 1
                    if level[ pop_sel_d[ pop_latency ] ] == 1:
                        empty.next[ pop_sel_d[ pop_latency ] ] = 1
            if temp_level >= depth-push_latency or num_free==0 or (num_free==1 and mem_we==1):
                full.next = 1
            else:
                full.next = 0
            tot_level.next = temp_level

    muw = push_latency-mem_input_flops
    mow = pop_latency-mem_input_flops

    # The fifo levels counted at the memory write clock cycle
    write_level = [ copySignal(tot_level) for _ in range(nr_of_queues) ]
    zwl = count_level(push_oh_d, pop_oh_d, write_level, clk, rstn, cycle=muw, name=name+".zwl")
    
    @always_comb
    def memw_comb():
        mem_we.next    = 0
        mem_wa.next    = 0
        mem_in.next    = 0
        skip1.next     = nr_of_queues
        skip0.next     = nr_of_queues
        # if push_d[ muw ]==1 and not ( empty[ push_sel_d[ muw ] ]==1 or ( level[ push_sel_d[ muw ] ]==1 and pop_d[ mow ]==1 and push_sel_d[ muw ]==pop_sel_d[ mow ] )):
        #for i in range(push_)
        if push_d[ muw ]==1 and write_level[ push_sel_d[ muw ] ] > 0:
            if write_level[ push_sel_d[ muw ] ] == 1 and push_oh_d[ muw ]==pop_oh_d[ muw ]:
                skip0.next = push_sel_d[ muw ]
            elif write_level[ push_sel_d[ muw ] ] == 1 and push_oh_d[ muw ]==pop_oh_d[ muw - 1 ]: # TODO generalize the last part
                skip1.next = push_sel_d[ muw ]
            else:
                mem_we.next     = 1
                mem_wa.next     = free_out
                mem_in.next     = idata_d[ muw ]
                     
    @always_comb
    def linkw_comb():
        link_we.next   = 0
        link_wa.next   = 0
        link_in.next   = 0
        if push_d[ muw ]==1 and write_level[ push_sel_d[ muw ] ] > 1:
            if write_level[ push_sel_d[ muw ] ] == 2 and push_oh_d[ muw ]==pop_oh_d[ muw ]:
                pass
            #elif write_level[ push_sel_d[ muw ] ] == 2 and push_oh_d[ muw ]==pop_oh_d[ muw - 1 ]: # TODO generalize the last part
            #    pass
            else:
                link_we.next    = mem_we
                link_wa.next    = tail[ push_sel_d[ muw ] ]
                link_in.next    = free_out
            
    poc = pop_latency-mem_input_flops-mem_output_flops-1
    puc = push_latency-mem_input_flops-mem_output_flops-1

    # The fifo levels counted at the memory read clock cycle
    read_level = [ copySignal(tot_level) for _ in range(nr_of_queues) ]
    zrl = count_level(push_oh_d, pop_oh_d, read_level, clk, rstn, cycle=poc, name=name+".zrl")
            
    @always_comb
    def memr_comb():
        mem_re.next    = 0
        mem_ra.next    = 0
        link_re.next   = 0
        link_ra.next   = 0
        if pop_d[ poc ]==1:
            if read_level[ pop_sel_d[ poc ] ] > 1 and not skip1_d[ poc ]==pop_sel_d[ poc ]: # TODO Generalize the last part
                mem_re.next     = 1
                mem_ra.next     = head[ pop_sel_d[ poc ] ]
            if read_level[ pop_sel_d[ poc ] ] > 2:
                link_re.next    = 1
                link_ra.next    = head[ pop_sel_d[ poc ] ]

    @always_comb
    def head_tail_comb():
        for i in range(nr_of_queues):
            head_next[i].next  = head[i]
            tail_next[i].next  = tail[i]
        # Head
        if push_d[ muw ]==1 and ( write_level[ push_sel_d[ muw ] ] == 1 or
                                  write_level[ push_sel_d[ muw ] ] == 2 and push_oh_d[muw]==pop_oh_d[muw]): # TODO: Generalize the last part
            head_next[ push_sel_d[ muw ] ].next = free_out 
        if link_re_d[ mem_input_flops+mem_output_flops+1 ]:
            head_next[ pop_sel_d[ pop_latency ] ].next = link_out
        # Tail
        #if push_d[ muw ]==1 and write_level[ push_sel_d[ muw ] ] > 0:
        #    tail_next[ push_sel_d[ muw ] ].next = free_out 
        if mem_we==1 and write_level[ push_sel_d[ 1 ] ] > 0:
            tail_next[ push_sel_d[ 1 ] ].next = free_out 
                
    @always(clk.posedge, rstn.negedge)
    def reg_process():
        if rstn==0:
            for i in range(nr_of_queues):
                head[i].next  = 0
                tail[i].next  = 0
                odata[i].next = 0
        else:
            for i in range(nr_of_queues):
                head[i].next  = head_next[i]
                tail[i].next  = tail_next[i]
                odata[i].next = odata_next[i]

    imem  = memory(mem_in, mem_out, mem_ra, mem_wa, mem_re, mem_we, clk, rstn,
                   depth       = mem_depth,
                   input_flops  = mem_input_flops,
                   output_flops = mem_output_flops,
                   name        = name+".imem")
    ilink = memory(link_in, link_out, link_ra, link_wa, link_re, link_we, clk, rstn,
                   depth         = mem_depth,
                   input_flops    = mem_input_flops,
                   output_flops   = mem_output_flops,
                   write_through = 1,
                   name          = name+".ilink")

    # Note that the fifo_m_latency is written with the assumption that free will be able to return
    # an address as long as there are less than depth number of used addresses, but that this is not
    # true for fifo_mem3, which can have as much as eight addresses milling around in its plumbing.
    # Thus fifo_m_latency cannot be used together with free_mem3.
    # /Per
    print("Warning! fifo_m_latency %s cannot use the free_matrix_mem3, thus the free_LIFO is forced here." % name)
    ifree = free_LIFO(
        idata    = mem_ra_d[3],
        odata    = free_out,
        push     = mem_re_d[3],
        pop      = mem_we,
        num_free = num_free,
        clk      = clk,
        rstn     = rstn,
        consistency_check = consistency_check,
        depth    = mem_depth,
        name     = name+".free")

    @always(clk.negedge, rstn.negedge)
    def assert_pop():
        if rstn==0:
            pass
        else:
            "synopsys translate_off"
            for i in range(nr_of_queues):
                popsum = pops[i] +  pop_oh_d[0][i]
                if popsum > 1:
                    assert False, "ERROR! fifo_m_latency %s %d pops within the latency period for queue %d" %(name, popsum, i)
            "synopsys translate_on"
    
    return instances()
