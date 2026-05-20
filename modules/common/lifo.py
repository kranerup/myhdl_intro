from myhdl import *
from .Common import pass_through, sliceSignal, signalType, copySignal, flop_e, multiflop
from .Common import flop
from .memory import memory
"""
File status: The lifo is as far as I know only used in the free-block
(for medium sizes). No need to fuss about it.

TODO: Redefine push==1 && pop==1 to a flop to get rid of the combinatorial path
TODO: Use read enable properly. 
"""

def lifo(idata,odata,push,pop,full,empty,level,clk,rstn,clear=0,depth=4,
         consistency_check=None,memoryMode='ff',
         memory_input_flops=0, memory_output_flops=0, name=""):
    
    assert clear==0, "%s LIFO has no support for clear yet"%name
    ff=0
    if depth <= (memory_input_flops+memory_output_flops+1)*3:
        ff=1
    if signalType(idata):
        if ((memory_input_flops>0 or memory_output_flops>0) and ff==0):
            iLifoslat = lifo_signal_lat(idata, odata, push, pop, full, empty, level, clk, rstn,
                                     clear, depth, memory_input_flops, memory_output_flops, name)
        else:
            if (memory_input_flops>0 or memory_output_flops>0) and ff==1:
                memoryMode='ff'
            iLifos = lifo_signal(idata, odata, push, pop, full, empty, level, clk, rstn,
                               clear, depth, memoryMode, memory_input_flops, memory_output_flops, name)
    elif type(idata).__name__ == "list":
        iLifol = lifo_list(idata, odata, push, pop, full, empty, level, clk, rstn,
                         clear, depth, memoryMode, memory_input_flops, memory_output_flops, name)
    else:
        print("ERROR! Unsupported type for lifo", name+":", type(idata).__name__)
        exit()
    return instances()

def lifo_list(idata,odata,push,pop,full,empty,level,clk,rstn,clear=0,depth=4,
              memoryMode='ff', memory_input_flops=0, memory_output_flops=0, name=""):
    if len(idata) == 1:
        iflat = Signal(intbv(0)[len(idata[0]):])
        iconnect = pass_through(idata[0], iflat, name=name+".iflat")
        oflat = Signal(intbv(0)[len(idata[0]):])
        oconnect = pass_through(oflat, odata[0], name=name+".oflat")
    else:
        iflat = ConcatSignal(*reversed(idata))
        totw = len(iflat)
        oflat = Signal(intbv(0)[totw:])
        oconnect = sliceSignal(oflat, odata)
    inst = lifo(iflat, oflat, push, pop, full, empty, level, clk, rstn, clear, depth,
                None, memoryMode, memory_input_flops, memory_output_flops, name)
    return instances()
    

def lifo_stat(push, pop, level, full, empty, depth, clk, rstn, just_push=None, just_pop=None, name=""):
    if just_push==None:
        just_push = copySignal(push)
    if just_pop==None:
        just_pop  = copySignal(pop)
    @always_comb
    def setjust():
        just_push.next = 0
        just_pop.next  = 0
        if push==1 and pop==0:
            just_push.next = 1
        if push==0 and pop==1:
            just_pop.next = 1

    @always(clk.posedge, rstn.negedge)
    def setStatus():
        if rstn==0:
            level.next = 0
            full.next  = 0
            empty.next = 1
        else:
            if just_push==1:
                level.next = level + 1
                if level == depth-1:
                    full.next = 1
                if level == 0:
                    empty.next = 0 
            if just_pop==1:
                level.next = level - 1
                if level == depth:
                    full.next = 0
                if level == 1:
                    empty.next = 1
    return instances()
    
def lifo_signal(idata,odata,push,pop,full,empty,level,clk,rstn,clear=0,
                depth=4,memoryMode='ff', memory_input_flops=0, memory_output_flops=0, name=""):
    if depth-2*(memory_input_flops+memory_output_flops)<2:
        memoryMode = 'ff'
    elif memoryMode == 'mem+ff':
        # Now 'mem' mode has a FF for input data
        memoryMode = 'mem'
    w = len(idata)
    tail    = Signal(intbv(0, min=-1, max=depth))
    tail_next    = Signal(intbv(0, min=-1, max=depth))
    writePtr  = Signal(intbv(0, min=0, max=depth))

    print("Instantiated lifo_signal %s in %s-mode with depth %s, memory_input_flops %s and memory_output_flops %s" % (name, memoryMode, depth, memory_input_flops, memory_output_flops))
    
    memlat = 1+memory_input_flops+memory_output_flops
    logic_high_i = Signal(intbv(1)[1:0])
    logic_high = Signal(intbv(1)[1:0])
    zPasshigh = pass_through(logic_high_i, logic_high, name=name+".lh")

    abs_push        = copySignal(push)
    abs_pop         = copySignal(pop)
        
    iStat = lifo_stat(push, pop, level, full, empty, depth, clk, rstn, abs_push, abs_pop, name=name+".iStat")

    if memoryMode=='ff':
        readPtr   = Signal(intbv(0, min=0, max=depth))
    indexWidth = len(writePtr)
    if memoryMode=='ff':
        data    = [Signal(intbv(0)[w:0]) for x in range(depth)]
    elif memoryMode=='mem':
        idata_d1 = copySignal(idata)
        push_d1 = copySignal(push)
        pop_d0 = copySignal(pop)
        zFpop = multiflop(pop, pop_d0, clk, rstn, depth=memory_input_flops+memory_output_flops, name=name+".zFpop") 
        zFpush = multiflop(push, push_d1, clk, rstn, depth=1+memory_input_flops+memory_output_flops, name=name+".zFpush") 
        zFid   = multiflop(idata, idata_d1, clk, rstn, depth=1+memory_input_flops+memory_output_flops, name=name+".zFid") 
        raddr = Signal(intbv(0, min=0, max=depth))
        waddr = Signal(intbv(0, min=0, max=depth))
        wenable = Signal(intbv(0)[1:0])
        renable = Signal(intbv(0)[1:0])
        renable_dd = Signal(intbv(0)[1:0])
        mem_idata = copySignal(idata)
        mem_odata = copySignal(odata)

        mem_tail        = Signal(intbv(0, min=-1, max=depth))
        mem_tail_next   = copySignal(mem_tail)

        @always_comb
        def setwen():
            if push==1:
                wenable.next = 1
            else:
                wenable.next = 0
                
        @always_comb
        def setren():
            if pop==1:
                if push==1 and (raddr==waddr):
                    renable.next = 0
                else:
                    renable.next = 1
            else:
                renable.next = 0
                
        @always_comb
        def setmemTail():
            mem_tail_next.next = mem_tail
            if push==1 and pop==0:
                if mem_tail < depth-1:
                    mem_tail_next.next = mem_tail+1
            if pop==1 and push==0:
                if mem_tail>=0:
                    mem_tail_next.next = mem_tail-1
                    
        @always(clk.posedge, rstn.negedge)
        def tailcnt():
            if rstn==0:
                mem_tail.next = -1
            else:
                mem_tail.next = mem_tail_next

        @always_comb
        def setwaddr():
            if mem_tail == depth-1:
                waddr.next = mem_tail[indexWidth:]
            elif mem_tail==-1:
                waddr.next = 0
            elif push==1 and pop==1:
                waddr.next = mem_tail[indexWidth:]
            else:
                waddr.next = mem_tail[indexWidth:] +1
                
        if memlat==1:        
            @always_comb
            def setraddr():
                if mem_tail==-1:
                    raddr.next = 0
                elif pop==1 and mem_tail>=1:
                    raddr.next = mem_tail[indexWidth:]-1
                else:
                    raddr.next = mem_tail[indexWidth:]
        else:
            @always_comb
            def setraddrml2():
                raddr.next = 0
                if mem_tail==-1:
                    raddr.next = 0
                elif pop==1:
                    raddr.next = mem_tail[indexWidth:]
    
        @always_comb
        def setodata():
            odata.next = mem_odata
            if push_d1==1 and pop_d0==1:
                odata.next = idata_d1
                
        mem = memory(idata,
                     mem_odata,
                     raddr = raddr,
                     waddr = waddr,
                     renable = logic_high if memlat==1 else renable,
                     wenable = wenable,
                     clk = clk,
                     rstn = rstn,
                     depth = depth,
                     write_through = 1 if memlat==1 else 0,
                     input_flops = memory_input_flops,
                     output_flops = memory_output_flops,
                     name=name+".mem")
        
    else:
        print("ERROR! Unsupported memoryMode", memoryMode)



    if memoryMode=='ff':
        @always_comb
        def setRead():
            if tail == -1:
                readPtr.next = 0
            else:
                readPtr.next = tail[indexWidth:]
        @always_comb
        def setWrite():
            if tail == depth-1:
                writePtr.next = tail[indexWidth:]
            elif tail==-1:
                writePtr.next = 0
            else:
                writePtr.next = tail[indexWidth:] + 1
        @always_comb
        def driveOut():
            odata.next = data[readPtr]
#     elif memoryMode=='mem':
#         @always_comb
#         def driveOut():
#             if push==1 and pop==1:
#                 odata.next = idata
#             elif pop_d1==1 and push_d1==0 and pop==1 and push==0:
#                 odata.next = mem_odata
#             else:
# #                odata.next = mem_output 
#                 odata.next = reg_odata
        

    @always_comb
    def setTail():
        tail_next.next = tail
        if push==1 and pop==0:
            if tail < depth - 1 :
                tail_next.next = tail + 1
        if pop==1 and push==0:
            if tail >= 0:
                tail_next.next = tail - 1

    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            tail.next  = -1
        else:
            tail.next = tail_next
            "synthesis translate_off"
            if push==1 and pop==0:
                if full==1:
                    print("ERROR pushing to full LIFO", name)
                    assert False
            if pop==1 and push==0:
                if empty:
                    print("ERROR popping empty LIFO", name)
                    assert False
            "synthesis translate_on"

    if memoryMode=='ff': 
        @always(clk.posedge, rstn.negedge)
        def fill():
            if rstn==0:
                for i in range(len(data)):
                    data[i].next = 0
            else:
                if push==1:
                    if pop==1:
                        data[writePtr-1].next = idata
                    else:
                        data[writePtr].next = idata
    return instances()

# lifo with 3cc memory access
def lifo_signal_lat(idata,odata,push,pop,full,empty,level,clk,rstn,
                    clear, depth=4, memory_input_flops=0, memory_output_flops=0, name=""):
    
    print("Instantiated lifo_signal_lat %s with depth %s, memory_input_flops %s and memory_output_flops %s" % (name, depth, memory_input_flops, memory_output_flops))
    
    ff_depth = 1+memory_input_flops+memory_output_flops
    w=len(idata)
    
    data    = [Signal(intbv(0)[w:0]) for x in range(ff_depth*2)]
    wPtr  = Signal(intbv(0, min=0, max=ff_depth*2+1))
    push_d1 = copySignal(push)
    zFpush = flop(push, push_d1, clk, rstn, name=name+".ZFpush")
    just_push = copySignal(push)
    just_pop  = copySignal(pop)
    
    iStat = lifo_stat(push, pop, level, full, empty, depth, clk, rstn, just_push, just_pop, name=name+".iStat")

    used_mem = Signal(modbv(0)[1:0])
    used_mem_n = Signal(modbv(0)[1:0])
    
    mlifo_depth = (depth//ff_depth)
    if depth%ff_depth:
        mlifo_depth += 1 
    
    mlifo_idata = Signal( modbv(0)[w*ff_depth:] )
    mlifo_odata = copySignal( mlifo_idata )
    mlifo_odata_split = [ copySignal( idata ) for i in range(ff_depth) ]
    zPassmlo = pass_through(mlifo_odata, mlifo_odata_split, name=name+".zPassmlo")
    
    mlifo_push = copySignal(  push) 
    mlifo_pop = copySignal(   pop)  
    mlifo_push_ff = copySignal(  push) 
    mlifo_pop_ff = copySignal(   pop)  
    mlifo_full = copySignal(  full) 
    mlifo_empty = copySignal( empty)
    mlifo_level = Signal( intbv(0, min=0, max=mlifo_depth+1) )
    mlifo_push_dd = copySignal(pop)
    mlifo_pop_dd = copySignal(pop)
    zDelaymlpush = multiflop(mlifo_push, mlifo_push_dd, depth=ff_depth, clk=clk, rstn=rstn, name=name+".zDelaymlpush")
    zDelaymlpop = multiflop(mlifo_pop, mlifo_pop_dd, depth=ff_depth, clk=clk, rstn=rstn, name=name+".zDelaymlpop")
    zFlpush = flop(mlifo_push, mlifo_push_ff, clk=clk, rstn=rstn, name=name+".zFlpush")
    zFlpop =  flop(mlifo_pop, mlifo_pop_ff, clk=clk, rstn=rstn, name=name+".zFlpop")
        
    iMlifo = lifo_signal(
        idata = mlifo_idata,
        odata = mlifo_odata,
        push =  mlifo_push, 
        pop =   mlifo_pop,  
        full =  mlifo_full, 
        empty = mlifo_empty,
        level = mlifo_level,
        clk =   clk,  
        rstn =  rstn, 
        clear = clear,
        depth = mlifo_depth,
        memoryMode = "mem",
        memory_input_flops = memory_input_flops,
        memory_output_flops = memory_output_flops,
        name = name+".iMlifo"
    )

    t_state = enum('pushing', 'popping', 'idle')
    state_n = Signal(t_state.idle)
    state = Signal(t_state.idle)
    @always_comb
    def cblock():
        ctmp = intbv(0, min=-ff_depth, max=ff_depth*4)
        ctmp[:] = wPtr + push - pop + (mlifo_pop_dd*ff_depth)
        used_mem_n.next = 0
        used_mem_tmp = modbv(0)[1:]
        state_n.next = state
        tmp = modbv(0)[w*ff_depth:]
        for i in range(ff_depth):
            tmp[:] = tmp | data[ff_depth+i] << (w*i)
        mlifo_idata.next = tmp
        mlifo_push.next = 0
        mlifo_pop.next = 0
        if mlifo_pop_dd==1 and (pop==1 and push_d1==0 and wPtr==0):
            used_mem_n.next = 1
            used_mem_tmp[:] = 1
            odata.next = mlifo_odata[w:]
        else:
            odata.next = data[0]
        if mlifo_push_dd==1 and state==t_state.pushing:
            state_n.next = t_state.idle
        if mlifo_pop_dd==1 and state==t_state.popping:
            state_n.next = t_state.idle
        if ctmp>ff_depth*2 and (state!=t_state.popping or mlifo_pop_dd==1) and mlifo_push_ff==0:
            state_n.next = t_state.pushing
            mlifo_push.next = 1
            if mlifo_pop_dd==1:
                mlifo_idata.next = mlifo_odata
                
        if ctmp<ff_depth and ((state==t_state.pushing and (mlifo_push_ff==0 or mlifo_push_dd==1)) or state==t_state.idle or mlifo_pop_dd==1) and mlifo_empty==0:
            state_n.next = t_state.popping
            mlifo_pop.next = 1

    fd2 = 2*ff_depth
    @always(clk.posedge, rstn.negedge)
    def setData():
        if rstn==0:
            used_mem.next = 0
            state.next = t_state.idle
            wPtr.next = 0
            for i in range(fd2):
                data[i].next = 0
        else:
            used_mem.next = used_mem_n
            state.next = state_n
            ptmp = intbv(0, min=-ff_depth, max=depth+1)
            ptmp[:] = wPtr
            if push==1:
                data[0].next = idata
            if just_push==1:
                for i in range(ff_depth*2-1):
                    data[i+1].next = data[i]
                ptmp[:] += 1
            if just_pop==1:
                for i in range(ff_depth*2-1):
                    data[i].next = data[i+1]
                ptmp[:] -= 1
            if mlifo_push==1:
                ptmp -= ff_depth
            if mlifo_pop_dd==1:
                ptmp += ff_depth
                if mlifo_push==0:
                    if (used_mem_n==1):
                        for i in range(ff_depth-1):
                            if wPtr+i+1+push-pop >= 0 and wPtr+i+1+push-pop < ff_depth*2:
                                data[wPtr+i+1+push-pop].next = mlifo_odata_split[i+1]
                    else:
                        for i in range(ff_depth):
                            if wPtr+i+push-pop >= 0 and wPtr+i+push-pop < ff_depth*2:
                                data[wPtr+i+push-pop].next = mlifo_odata_split[i]
            "synthesis translate_off"
            if ptmp > ff_depth*2:
                print("Assertion ERROR! %s ptmp %s > ff_depth*2 %s" % (name, ptmp, ff_depth*2))
                assert False
            "synthesis translate_on"
            wPtr.next = ptmp
    return instances()
        
