from myhdl import *
from .Common import pass_through, signalType, listType, modInc, copySignal
from .Common import compoundWidth, mux2, flop_e, flop, pipeline
from .memory import memory
import sys

def fifo_signal_output_latency(idata,odata,push,pop_request,full,empty,
                               level,clk,rstn,memory_input_flops, memory_output_flops, clear=0,depth=8, name=""):
    """
    A fifo where the memory can have latency > 1. 
    The odata is delayed by the memory latency
    """
    
    w = len(idata)
    head_next    = Signal(intbv(0, min=0, max=depth))
        # next read address to memory
    tail_next    = Signal(intbv(0, min=0, max=depth))
        # next write address to memory
    head    = Signal(intbv(0, min=0, max=depth))
        # read address to memory
    tail    = Signal(intbv(0, min=0, max=depth))
        # write address to memory

    mem_odata = copySignal(odata)

    mem = memory(idata, mem_odata, head, tail, pop_request, push,
                 clk, rstn, depth=depth, write_through=1, input_flops=memory_input_flops,
                 output_flops=memory_output_flops, name=name+".mem")

    @always_comb
    def driveout():
        odata.next = mem_odata

    @always_comb
    def setHeadNext():
        head_next.next = head
        if pop_request==1:
            head_next.next = modInc(head)

    @always_comb
    def setTail():
        tail_next.next = tail
        if push==1:
            tail_next.next = modInc(tail)

    from modules.common.fifo_imp import fifo_counters
    zFcnt = fifo_counters(push, pop_request, level, empty, full, clear, clk, rstn, depth, name=name+".zFcnt")

    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            tail.next  = 0
            head.next  = 0
        else:
            if clear==1:
                head.next = 0
                tail.next = 0
            else:
                head.next = head_next
                tail.next = tail_next

    return instances()


def fifo_signal_memlat(
        idata, odata, push, pop, full, empty, level, clk, rstn, memory_input_flops, memory_output_flops, 
        clear=0, depth=8, consistency_check=None, name=""):
    """
    A well behaving fifo with memory flops. 
    It is built from a fifo with output latency (fifo1), followed by a 
    shallow fifo without output latency (fifo2). There is also a pipeline 
    to bypass fifo1. 
    I actually think the shallow fifo is uneccessary. The same functionality
    could be achieved using only fifo1 and a stallable pipeline. /P
    """

    assert not signalType(clear)
    
    # optional check mechanism to investigate if fifo is empty
    if signalType(consistency_check):
        assert_ccheck = Signal(intbv(0)[1:0])
        @always(clk.posedge, rstn.negedge)
        def ccheck():
            if rstn==0:
                assert_ccheck.next = 0
            else:
                assert_ccheck.next = 0
                if consistency_check==1:
                    "synthesis translate_off"
                    print("Consistency check", name)
                    "synthesis translate_on"
                    if empty==0:
                        assert_ccheck.next = 1
                        "synthesis translate_off"
                        assert False, (("%s: Consistency check FAILED! level %d") % (name,level))
                        "synthesis translate_on"        
    
    w = len(idata)
    
    fifo1_latency = 1+memory_input_flops+memory_output_flops
    print("Instantiated fifo_signal_memlat %s with depth %s, memory_input_flops %s, memory_output_flops %s" %(name, depth, memory_input_flops, memory_output_flops))
    sys.stdout.flush()
    fifo1_idata = copySignal(idata)
    fifo1_odata = copySignal(odata)
    fifo1_push = Signal(intbv(0)[1:0])
    fifo1_pop = Signal(intbv(0)[1:0])
    fifo1_full = Signal(intbv(0)[1:0])
    fifo1_empty = Signal(intbv(0)[1:0])
    fifo1_level = copySignal(level)
    iFifo1 = fifo_signal_output_latency(
        fifo1_idata, fifo1_odata,
        fifo1_push, fifo1_pop,
        fifo1_full, fifo1_empty, fifo1_level,
        clk, rstn,
        clear=clear, depth=depth,
        memory_input_flops  = memory_input_flops,
        memory_output_flops = memory_output_flops,
        name=name + '.iFifo1')

    fifo2_depth = fifo1_latency+1
    fifo2_idata = copySignal(idata)
    fifo2_odata = copySignal(odata)
    fifo2_push = Signal(intbv(0)[1:0])
    fifo2_pop = Signal(intbv(0)[1:0])
    fifo2_full = Signal(intbv(0)[1:0])
    fifo2_empty = Signal(intbv(0)[1:0])
    fifo2_level = copySignal(level)
    from modules.common.fifo_imp import fifo_signal
    iFifo2 = fifo_signal(
        fifo2_idata, fifo2_odata, fifo2_push, fifo2_pop,
        fifo2_full, fifo2_empty, fifo2_level,
        clk, rstn,
        clear=clear, depth=fifo2_depth, memoryMode='ff',
        name=name + '.iFifo2')

    popped = Signal(intbv(0, min=0, max=fifo1_latency+1))
    passed = Signal(intbv(0, min=0, max=fifo1_latency+1))
    
    fifo1_pdata   = [ copySignal(fifo1_idata) for _ in range(fifo1_latency) ]
    fifo1_pdata_n = [ copySignal(fifo1_idata) for _ in range(fifo1_latency) ]
    from modules.common.Common import multiflop
    fifo1_pass    =  Signal(modbv(0)[fifo1_latency:0])
    fifo1_pass_n  =  Signal(modbv(0)[fifo1_latency:0])
    
    fifo1_pop_d = Signal(modbv(0)[fifo1_latency:0])
    @always(clk.posedge, rstn.negedge)
    def pipe():
        if rstn==0:
            fifo1_pop_d.next = 0
            fifo1_pass.next = 0
            for i in range(0, fifo1_latency):
                fifo1_pdata[i].next = 0
        else:
            fifo1_pop_d.next = (fifo1_pop_d << 1) + fifo1_pop
            fifo1_pass.next = fifo1_pass_n
            for i in range(0, fifo1_latency):
                fifo1_pdata[i].next = fifo1_pdata_n[i]
            
    from modules.common.Common import count_ones

    pw = len(passed)
    @always_comb
    def cpass():
        tmp = modbv(0)[pw:0]
        for i in range(fifo1_latency):
            if fifo1_pass[i]==1:
                tmp[:] += 1
        passed.next = tmp
        
    @always_comb
    def cpop():
        tmp = modbv(0)[pw:0]
        for i in range(fifo1_latency):
            if fifo1_pop_d[i]==1:
                tmp[:] += 1
        popped.next = tmp
        
    first_avail_pass = Signal(intbv(0, min=0, max=fifo1_latency+1))

    transit = Signal(modbv(0)[(fifo1_latency+1+fifo2_depth+1).bit_length():])
    @always_comb
    def trst():
        transit.next = fifo2_level+popped+passed-pop
        first_avail_pass.next = fifo1_latency-1
        for i in downrange(fifo1_latency-1, 0):
            if fifo1_pass[i]==1 or fifo1_pop_d[i]==1:
                first_avail_pass.next = i
                
    dirty_odata = copySignal(odata)
    @always_comb
    def ctrl():
        fifo1_pop.next = 0
        fifo1_push.next = 0
        fifo1_idata.next = 0
        fifo2_pop.next = 0
        fifo2_push.next = fifo1_pop_d[fifo1_latency-1] if fifo1_pass[fifo1_latency-1]==0 else 1
        fifo2_idata.next = fifo1_odata if fifo1_pass[fifo1_latency-1]==0 else fifo1_pdata[fifo1_latency-1]
        fifo1_pass_n.next = (fifo1_pass << 1)
        fifo1_pdata_n[0].next = 0
        for i in range(1, fifo1_latency):
            fifo1_pdata_n[i].next = fifo1_pdata[i-1]
        if push==1:
            # If there is nothing queued before fifo2
            if fifo1_level==0 and fifo1_pop_d==0 and fifo1_pass==0:
                # If fifo2 can accept a push
                if fifo2_full==0:
                    fifo2_push.next = 1
                    fifo2_idata.next = idata
                else:
                    fifo1_push.next = 1
                    fifo1_idata.next = idata
            else: # There is stuff before fifo2
                # If fifo1 is empty, there is data in flight to fifo2
                # but not enough to fill fifo2, then pass through fifo1
                if fifo1_empty==1 and transit<fifo2_depth:
                    fifo1_pass_n.next[first_avail_pass] = 1
                    fifo1_pdata_n[first_avail_pass].next = idata
                else:
                    fifo1_push.next = 1
                    fifo1_idata.next = idata
                # If fifo2 can accept a new push
                if transit<fifo2_depth and fifo1_level>0:
                    fifo1_pop.next = 1
                # If fifo2 will be pushed
                #if fifo1_pop_d[fifo1_latency-1]==1 or fifo1_pass[fifo1_latency-1]==1:
                #    "synthesis translate_off"
                #    if fifo2_full==1:
                #        print "%s ERROR! Pushing full fifo2" % name
                #        assert False
                #    "synthesis translate_on"
        else: # push==0
            if transit<fifo2_depth and fifo1_level>0:
                fifo1_pop.next = 1
        if pop==1 and fifo2_empty==1:
            fifo2_push.next = 0
            #"synthesis translate_off"
            #if fifo1_pop_d[fifo1_latency-1]==0:
            #    print "%s ERROR! Popping empty fifo2" % name
            #    assert False
            #"synthesis translate_on"
        else:
            fifo2_pop.next = pop
        if fifo2_empty==1:
            dirty_odata.next = fifo1_odata if fifo1_pass[fifo1_latency-1]==0 else fifo1_pdata[fifo1_latency-1]
        else:
            dirty_odata.next = fifo2_odata
            
    # sanity checks
            
    push_full = Signal(modbv(0)[1:0], debug_level=1)
    pop_empty = Signal(modbv(0)[1:0], debug_level=1)
    
    @always(clk.posedge, rstn.negedge)
    def assertions():
        if rstn==0: # We have to write like this to make it look like a flop /P
            push_full.next = 0
            pop_empty.next = 0
        else:
            if clear==0:
                if push==1:
                    if full==1:
                        push_full.next = 1
                        "synthesis translate_off"                        
                        print("ERROR pushing to full fifo_mem3 %s" % name)
                        assert False
                        "synthesis translate_on"                        
                if pop==1:
                    if empty==1:
                        pop_empty.next = 1
                        "synthesis translate_off"
                        print("ERROR popping empty fifo_mem3", name)
                        assert False
                        "synthesis translate_on"

    # Counters
    dirty_level = copySignal(level)
    dirty_empty = copySignal(empty)
    from modules.common.fifo_imp import fifo_counters
    zFcnt = fifo_counters(push, pop, dirty_level, dirty_empty, full, clear, clk, rstn, depth, name=name+".zFcnt")
    
    from .fifo_async import clean_fifo_output
    igate = clean_fifo_output(dirty_empty, empty, dirty_odata, odata, clk, rstn, dirty_level, level)                 
    return instances()
