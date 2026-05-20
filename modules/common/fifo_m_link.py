from myhdl import *
from .Common import pass_through, signalType, listType, modInc, compoundWidth, flop, slice2matrix, listOfSignalsType, mux_list, pipeline, copySignal
from modules.common.free import free, free_flop
from .memory import *
import sys

def fifo_m_link(idata,odata,push_enable,push_sel,pop_enable,pop_sel,full,empty,level,tot_level,clk,rstn,consistency_check,depth=4,input_flops=0,output_flops=0,push_latency=0, pop_latency=0, two_and_up=None, name=""):

    nr_of_queues = len(odata)
    mem_depth = depth
    mem_lat = 1 + input_flops + output_flops
    pd = mem_lat + 1
    
    head    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]
    tail    = [ Signal(intbv(0, min=0, max=mem_depth)) for _ in range(nr_of_queues) ]
    use_full = 1
    if full==None:
        use_full = 0
        
    
    iw    = len(idata)
    addrw = len(head[0])
    restw = iw-addrw
    print("Instanciated fifo_m_link %s with depth=%d, nr_of_queues=%d, mem_depth=%d, iw=%s, addrw=%s. restw=%s, mem_lat=%s"%(name, depth, nr_of_queues, mem_depth, iw, addrw, restw, mem_lat))
    print(name, "idata", idata)
    print(name, "empty", empty)
    
    sys.stdout.flush()
    link_in  = copySignal(idata)
    link_out = copySignal(link_in)
    link_ra  = Signal(modbv(0)[addrw:])
    link_wa  = Signal(modbv(0)[addrw:])
    link_re  = Signal(intbv(0)[1:0])
    link_we  = Signal(intbv(0)[1:0])
    iaddr = Signal(modbv(0)[addrw:])
    # irest = Signal(modbv(0)[restw:]) 
    link_addr = Signal(modbv(0)[addrw:])
    # link_rest = Signal(modbv(0)[restw:])
    
    @always_comb
    def splitid():
        iaddr.next = idata[addrw:]
        # irest.next = idata[:addrw]
        link_addr.next = link_out[addrw:]
        # link_rest.next = link_out[:addrw]
    
    out_reg = copySignal(odata)

    level_is_one       = Signal(intbv(0)[nr_of_queues:])
    level_is_two       = Signal(intbv(0)[nr_of_queues:])
    level_is_three     = Signal(intbv(0)[nr_of_queues:])
    level_two_and_up   = Signal(intbv(0)[nr_of_queues:])
    # level_three_and_up = Signal(intbv(0)[nr_of_queues:])
    if two_and_up!=None:
        zTwo_and_up = pass_through(level_two_and_up, two_and_up, name=name+".zTwoandup")
    
#    tot_level = Signal(intbv(0, min=0, max=mem_depth+1+nr_of_queues))

    consistency_check  = Signal(intbv(0)[1:0])

    free_out = copySignal(head[0])
    num_free = copySignal(tot_level)

    zFlop = []
    next_link_re = copySignal(link_re)
    next_link_ra = copySignal(link_ra)
    link_re_d = Signal(modbv(0)[mem_lat+1:]) 
    
    link_we_d = Signal(modbv(0)[pd+1:])  
    pop_enable_d = Signal(modbv(0)[pd+1:]) 
    pop_sel_d    = [ copySignal(pop_sel)    for _ in range(pd+1) ] 
    zFlop.append(pipeline(link_re,    link_re_d, clk, rstn))

    zFlop.append(pipeline(link_we,    link_we_d, clk, rstn))
    zFlop.append(pipeline(pop_enable, pop_enable_d, clk, rstn))
    zFlop.append(pipeline(pop_sel,    pop_sel_d, clk, rstn))

    # link_ra_d = [ copySignal(link_ra) for _ in range(pd+1) ]
    # link_wa_d = [ copySignal(link_wa) for _ in range(pd+1) ] 
    # zFlop.append(pipeline(link_ra,    link_ra_d, clk, rstn))
    # zFlop.append(pipeline(link_wa,    link_wa_d, clk, rstn))
    
    
    iLinkmem = memory(link_in, link_out, link_ra, link_wa, link_re, link_we, clk, rstn, depth=mem_depth, write_through=0, input_flops=input_flops, output_flops=output_flops, name=name+".iLinkmem")

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
            if link_re_d[mem_lat]==1:
                out_reg[pop_sel_d[mem_lat]].next = link_out
            if push_enable==1 and empty[push_sel]==1:
                out_reg[push_sel].next = idata
            if push_enable==1 and pop_enable==1 and push_sel==pop_sel and level_is_one[push_sel]==1:
                out_reg[push_sel].next = idata
            elif pop_enable==1 and level_is_one[pop_sel]==1:
                out_reg[pop_sel].next = 0
            
###
    tlw = len(tot_level)
    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            tot_level.next = 0
            if use_full==1:
                full.next = 0
            empty.next = (1<<nr_of_queues) - 1
            level_is_one.next = 0
            level_is_two.next = 0
            level_is_three.next = 0
            level_two_and_up.next = 0
            # level_three_and_up.next = 0
            for i in range(nr_of_queues):
                tail[i].next  = 0
                head[i].next  = 0
                level[i].next = 0
        else:
            # level_max_next = 0
            temp_level = modbv(0)[tlw:]
            temp_level[:] = tot_level
            if link_re_d[mem_lat]==1:
                head[pop_sel_d[mem_lat]].next = link_addr
            if push_enable==1:
                if empty[push_sel]==1 or (level_is_one[push_sel]==1 and pop_enable==1 and push_sel==pop_sel):
                    head[push_sel].next = iaddr
            if push_enable==1:
                tail[push_sel].next = iaddr

            if not (push_enable==1 and pop_enable==1 and push_sel==pop_sel):
                if push_enable==1:
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
                        # level_three_and_up.next[push_sel] = 1
                    if level_is_three[push_sel]==1:
                        level_is_three.next[push_sel] = 0

                    # "synthesis translate_off"
                    # if full==1:
                    #     print "ERROR pushing to full FIFO %s queue %d" % (name, push_sel)
                    #     assert False
                    # "synthesis translate_on"
                    level[push_sel].next = level[push_sel] + 1
                    temp_level[:] = temp_level + 1
                if pop_enable==1:
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
                        # level_three_and_up.next[pop_sel] = 0
                    if level[pop_sel]==4:
                        level_is_three.next[pop_sel] = 1
                    "synthesis translate_off"
                    if empty[pop_sel]==1:
                        print("ERROR popping empty FIFO %s queue %d" % (name, pop_sel))
                        assert False
                    "synthesis translate_on"
                    level[pop_sel].next = level[pop_sel] - 1
                    temp_level[:] = temp_level - 1
                    
            tot_level.next = temp_level
            if use_full==1:
                if (mem_depth-temp_level<mem_lat and link_we_d>0) or temp_level>=depth: 
                    full.next = 1
                else:
                    full.next = 0

    # Memory push
    @always_comb
    def mempush():
        if empty[push_sel]==0:
            link_in.next = idata
            link_wa.next = tail[push_sel]
            if push_enable==1 and not (pop_enable==1 and push_sel==pop_sel and level_is_one[push_sel]==1):
                link_we.next = 1
            else:
                link_we.next = 0
        else:
            link_in.next = 0
            link_wa.next = 0
            link_we.next = 0

    @always_comb
    def reading():
        if pop_enable==1 and level_two_and_up[pop_sel]==1:
            if link_re_d[mem_lat]==1 and pop_sel_d[mem_lat]==pop_sel:
                link_ra.next = link_addr
            else:
                link_ra.next = head[pop_sel]
            link_re.next = 1
        else:
            link_ra.next = 0
            link_re.next = 0

            
    @always_comb
    def driveout():
        for i in range(nr_of_queues):
            if link_re_d[mem_lat]==1 and pop_sel_d[mem_lat]==i:
                odata[i].next = link_out
            else:
                odata[i].next = out_reg[i]

    @always(clk.posedge, rstn.negedge)
    def assertFree():
        if rstn==0:
            pass
        else:
            "synthesis translate_off"
            if tot_level == 0:
                for i in range(len(level)):
                    if level[i]!=0:
                        print("ERROR!", name, "Level counter discrepancy. tot_level =", tot_level, "level[", i, "] =", level[i])
                        assert False
            if consistency_check==1:
                if empty==0 or tot_level!=0:
                    assert False, ("Consistency ERROR! fifo level %s != 0 for %s" % (tot_level, name))
            "synthesis translate_on"
                

    return instances()
