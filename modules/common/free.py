from myhdl import *
from .Common import pass_through, sliceSignal, signalType, select_rr, compoundWidth
from .Common import count_ones, flop, flop_e, pipeline, copySignal
from .fifo_imp import fifo_signal
from .memory import memory, memory_init
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()

"""
File status:

Free_matrix_mem3 needs to be timing optimized.

For intermediate depths it could perhaps be worth while to make a matrix type
free with a flop array as storage.
"""

# 72 and 79 characters
#2345678_112345678_212345678_312345678_412345678_512345678_612345678_712 456789

def free(idata, odata, push, pop, num_free, consistency_check, clk, rstn,
         error=None, depth=4, fm_width='default', mode='default', _generate=0, name=""):
    """
    A resource manager keeping track of the utilization of bufffer 
    addresses. 
    For smaller address spaces flip-flops are used. 
    For large address spaces a Free matrix is used.
    """
    # print 'depth=', str(depth), ' type=', type(depth)     
    # print 'fm_width=', str(fm_width), ' type=', type(fm_width)

    # If there is an error output, we shall not assert for pops
    # from an empty free, but instead gracefully issue an error

    print("Instenciated free %s with mode %sm fm_width %s and depth %s" % (name, mode, fm_width, depth))
    assert num_free.max >= depth, "ERROR! %s num_free (max %s) needs to be able to hold the depth %s" % (name, num_free.max-1, depth)
    if signalType(error):
        popf = copySignal(pop)
        @always_comb
        def filterpop():
            if pop==1 and num_free==0:
                popf.next = 0
                error.next = 1
            else:
                popf.next = pop
                error.next = 0
    else:
        popf=pop

    debug_list = [push, pop, idata, odata, num_free]
    if error!=None:
        debug_list = [error]+debug_list
    debug_free = Signal(intbv(0)[compoundWidth(debug_list):0], debug_level=1)
    zPassdbg = pass_through(debug_list, debug_free, name=name+".zPassdbg")

    freeFlag = Signal(intbv(0)[depth:])
    freeError= Signal(intbv(0)[depth:])

    # Turn on to report the non-free addresses at consistency check (and see verilator explode)
    debugdealloc = False 
    
    @checker(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            for i in range(len(freeFlag)):
                freeFlag.next[i] = 1
                freeError.next[i] = 0
        else:            
            if not (push==1 and popf==1 and idata==odata):
                if push==1:
                    if freeFlag[idata]==1:
                        print("ERROR for %s! Pushing already free addr %s"  %(
                            name, idata))
                        freeError.next[idata] = 1
                    freeFlag.next[idata] = 1
                if popf==1:
                    if freeFlag[odata]==0:
                        print("ERROR for %s! Popping non-free addr %s"  %(
                            name, odata))
                        freeError.next[odata] = 1
                    freeFlag.next[odata] = 0
            if push==1:
                print("%s Pushing addr %s"  %(
                        name, idata))
            if popf==1:
                print("%s! Popping addr %s"  %(
                name, odata))
            if debugdealloc:    
                if consistency_check==1:
                    for i in range(len(freeFlag)):
                        if freeFlag[i]==0:
                            assert False, ("Consistency ERROR! Address %s is not free" % i)
                    for i in range(len(freeFlag)):
                        if freeError[i]==1:
                            assert False, ("Consistency ERROR! Address %s flagged for dealloc error!" % i)
    
    if mode=='default':
        fmode = hwconf.free_config['mode']
        print(name, "mode=default -> mode %s from HwConf.free_config %s" % (hwconf.free_config["mode"], hwconf.free_config)) 
    else:
        fmode = mode
    if depth <=16:
        # print 'FREEFLOP'
        iFreeflop = free_flop(
            idata, odata, push, popf, num_free, consistency_check,
            clk, rstn, depth=depth, fm_width=None, name=name+".iFreeflop")        
    elif 'lifo' in fmode or 'fifo' in fmode:
        print(name, "lifo or fifo in mode")
        if "3cc" in fmode:
            print(name, "3cc in mode")
            memoryMode = "3cc"
        else:
            memoryMode = "mem"
        print(name, "memoryMode", memoryMode)
        if 'lifo' in fmode:
            qmode = 'lifo'
        elif 'fifo' in fmode:
            qmode = 'fifo'
            
        iFreelifo = free_LIFO(
            idata, odata, push, popf, num_free, consistency_check,
            clk, rstn, depth=depth, fm_width=None, memoryMode=memoryMode, queueMode=qmode, name=name+".iFreelifo")        
    else:
        # print 'FREE MEM3!!!'
        if fm_width=='default':
            fmw = hwconf.free_config['fm_width']
        else:
            fmw = fm_width
        print(name, "free_matrix_mem3 mode. fm_width=%s"%fmw)
        iFreemem3 = free_matrix_mem3(
            idata, odata, push, popf, num_free, consistency_check,
            clk, rstn, b_depth=depth, fm_width=fmw, name=name+".iFreemem3")
        
    return instances()

def free_LIFO(
        idata, odata, push, pop, num_free,
        consistency_check,clk,rstn,
        depth=40, fm_width=None, memoryMode="mem", queueMode="lifo", name=""):
    """
    A lifo implementation of free (for medium shallow depths)
    """
    initCnt   = Signal(intbv(0, min=0, max=depth+1))
    lodata    = Signal(intbv(0, min=0, max=depth))
    level     = Signal(intbv(0, min=0, max=depth+1))
    fi        = Signal(intbv(0, min=0, max=depth))
    fe        = Signal(intbv(0)[1:0])
    lpush     = Signal(intbv(0)[1:0])
    lpop      = Signal(intbv(0)[1:0])
    empty     = Signal(intbv(0)[1:0])
    full      = Signal(intbv(0)[1:0])
    data_width = len(idata)
    
    print("Instantiated free_LIFO %s in %s mode with depth %d" %(name, memoryMode, depth))

    memory_input_flops = 0
    memory_output_flops = 0
    if memoryMode == "3cc":
        memory_input_flops = 1
        memory_output_flops = 1
    
    idone = Signal(modbv(0)[1:])
    @always(clk.posedge, rstn.negedge)
    def setidone():
        if rstn==0:
            idone.next = 0
        else:
            if initCnt == depth-1 and pop==1:
                idone.next = 1
                
    @always(clk.posedge, rstn.negedge)
    def init():
        if rstn==0:
            initCnt.next = 1
        else:
            if idone==0:
                if pop==1:
                    initCnt.next = initCnt + 1
    if queueMode=="lifo":
        from .lifo import lifo as queue
    elif queueMode=="fifo":
        from .fifo import fifo as queue
    else:
        print(name, "unknown queueMode", queueMode)
        assert False
                    
    flifo = queue(idata    = idata,
                 odata    = lodata,
                 push     = lpush,
                 pop      = lpop,
                 full     = full,
                 empty    = empty,
                 level    = level,
                 clk      = clk,
                 rstn     = rstn,
                 depth    = depth,
                 memoryMode = 'mem',
                 memory_input_flops = memory_input_flops,
                 memory_output_flops = memory_output_flops,
                 name       = name+'.lifo')

    outflop   = flop_e(fi, odata, fe, clk, rstn, reset_value=0,
                       name=name+".outflop")

    @always_comb
    def setpop():
        if (initCnt==depth) and (num_free>1):
            lpop.next = pop
        else:
            lpop.next = 0

    @always_comb
    def setpush():
        if num_free>1 or (num_free==1 and pop==0):
            lpush.next = push
        else:
            lpush.next = 0

    @always_comb
    def setfe():
        if num_free>1:
            fe.next = pop
        elif num_free==0:
            fe.next = push
        elif num_free==1 and pop==1:
            fe.next = push
        else:
            fe.next = 0

    @always_comb
    def setodata():
        if initCnt == depth:
            if num_free<2:
                fi.next = idata
            else:
                fi.next = lodata
        else:
            fi.next = initCnt[data_width:]

    maxnf = num_free.max
    @always(clk.posedge, rstn.negedge)
    def setnumfree():
        if rstn==0:
            num_free.next = depth
        else:
             if push==1 and pop==0:
                "synthesis translate_off"
                if num_free == maxnf-1:
                    print("ERROR! num_free overflow for %s" % name)
                "synthesis translate_on"
                num_free.next = num_free + 1
             if push==0 and pop==1:
                "synthesis translate_off"
                if num_free == 0:
                    print("ERROR! num_free underflow for %s" % name)
                "synthesis translate_on"
                num_free.next = num_free - 1

    @always(clk.posedge, rstn.negedge)
    def consistency():
        if rstn==0:
            pass
        else:
            if consistency_check==1:
                "synopsys translate_off"
                print("Consistency check %s" % (name))
                if num_free != depth:
                    assert False, ("%s Consistency check FAILED! num_free %s < depth %s" % (name, num_free, depth))
                if level+depth+1-initCnt != depth:
                    assert False, ("%s Consistency check FAILED! level %s + depth %s + 1 - initCnt %s = %s < depth %s" % (name, level, depth, initCnt, level+depth+1-initCnt, depth))
                "synopsys translate_on"
    return instances()

def free_flop(
        idata, odata, push, pop, num_free,
        consistency_check,clk,rstn,
        depth=4, fm_width=None, name=""):
    """
    A flip-flop implementation of free (Only usable for really shallow depths)
    """
    freeFlag = Signal(intbv(0)[depth:])
    odata_next = Signal(intbv(0, min=0, max=depth))
    len_num_free = len(num_free)

    print("Instantiated free_flop %s with depth %d" %(name, depth))

    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn==0:
            for i in range(len(freeFlag)):
                freeFlag.next[i] = 1
        else:
            if push==1:
                "synthesis translate_off"
                if freeFlag[idata]==1:
                    print("ERROR for %s! Pushing already free addr %s"  %(
                        name, idata))
                "synthesis translate_on"
                freeFlag.next[idata] = 1
            if pop==1:
                "synthesis translate_off"
                if num_free==0:
                    print("ERROR for %s! Popping when num_free = 0"  %(name))
                if freeFlag[odata]==0:
                    print("ERROR for %s! Popping non-free addr %s"  %(
                        name, odata))
                "synthesis translate_on"
                freeFlag.next[odata] = 0

    @always_comb
    def setout():
#        if push==1 and pop==1:
#            odata.next = idata
#        else:
        odata.next = odata_next

    last = Signal(intbv(0, min=0, max=depth))
    valid = Signal(intbv(0)[1:])

    ff  = flop_e(odata, last, pop, clk, rstn)
    sel = select_rr(freeFlag, last, odata_next, valid, name=name+".selrr")

    @always_comb
    def cones(): 
        num_free.next = count_ones(freeFlag, w=len_num_free)
            
#    @always_comb
#    def findNumFree():
#        freeCnt = intbv(0)[len_num_free:0]
#        odata_next.next = 0
#        for i in range(len(freeFlag)):
#            if freeFlag[i]:
#                freeCnt += 1
#                odata_next.next = intbv(i)[len(odata):]
#        num_free.next = freeCnt

    
    @always(clk.posedge, rstn.negedge)
    def consistency():
        if rstn==0:
            pass
        else:
            if consistency_check==1:
                "synopsys translate_off"
                for i in range(len(freeFlag)):
                    if freeFlag[i]==0:
                        assert False, ("%s Consistency check FAILED! Address not freed addr %d" % (name, i))
                "synopsys translate_on"
                
    return instances()

def free_matrix(idata,odata,push,pop,num_free,doing_init,consistency_check,
                clk,rstn,depth=40,width=None,name=""):
    """
    A matrix implementation of free, for high depths. 
    (For really-high depths we could make a free_matrix_matrix, 
    where the free addresses for each line is also in a matrix... and so on)

    A memory contains bit flags for each free address. 
    The flags are set to one when an address is occupied 
    (and when it is moved to next_free).

    avail is a vector of flags indicating whether there are any 
    free addresses in each line in the memory. 

    For higher memory latency a number of free addresses need to 
    be kept in a fifo

    At pop:
    -The address in odata is returned, and replaced with one from the small fifo
    -The the memory is read for a line with free addresses
    -When the memory data returns, the fifo is replenished and the avail flag is updated,
    -The memory line updated and written back

    At push:
    -If num_free is 0 the address is put in odata, else...
    -If there is space in the fifo, it is put there, else...
    -The corresponding memory line is read
    -When the memory data returns, the fifo is replenished and the avail flag is updated,
    -The memory line updated and written back

    Note that the two last items are the same for push and pop.
    When memory data is available, why it was read makes no difference

    Simultaneous push and pop returns the address in odata, and puts 
    the pushed address in odata.

    The begun implementation below does not reflect the destription above 
    very well, and needs to be changed. /P
    """
    initCnt   = Signal(intbv(0, min=0, max=depth+1))
    lodata    = Signal(intbv(0, min=0, max=depth))
    level     = Signal(intbv(0, min=0, max=depth+1))
    fi        = Signal(intbv(0, min=0, max=depth))
    fe        = Signal(intbv(0, min=0, max=depth))
    lpush     = Signal(intbv(0)[1:0])
    lpop      = Signal(intbv(0)[1:0])
    empty     = Signal(intbv(0)[1:0])
    full      = Signal(intbv(0)[1:0])
    data_width = len(idata)
    next_line_oh = Signal(intbv(0)[memory_depth:])
    last_line_oh = Signal(intbv(0)[memory_depth:])

    iline = copySignal(waddr)
    icol  = Signal(intbv(0)[len(idata)-len(iline):])
    oline = copySignal(iline)
    ocol  = copySignal(icol)

    memory_depth_w = (memory_depth-1).bit_length()
    memory_width_w = (memory_width-1).bit_length()

    assert (memory_depth_w+memory_width_w)==len(idata)
    
    assert False, "Not yet implemented"

    if width==None:
        memory_width = 32 
    else:
        memory_width = width
    memory_depth = depth//memory_width
    
    waddr = Signal(intbv(0)[(memory_depth-1).bit_length():])
    raddr = copySignal(waddr)
    renable = Signal(intbv(0)[1:])
    wenable = Signal(intbv(0)[1:])
    rdata   = Signal(intbv(0)[memory_width-1:])
    wdata   = Signal(intbv(0)[memory_width-1:])

    if hwconf.memory_mode == 'inferred':
        consistency_data = [
            Signal(intbv(0)[memory_width-1:]) for _ in range(memory_depth) ]
    else:
        print("Warning: No consistency check for", name, " due to memory mode", hwconf.memory_mode)
        consistency_data = None

    next_free  = [ copySignal(waddr) for _ in range(memory_depth) ]
    next_avail = Signal(intbv(0)[memory_depth:])
    set   = Signal(intbv(0)[1:0])
    clear = Signal(intbv(0)[1:0])
    
    @always(clk.posedge, rstn.negedge)
    def init():
        if rstn==0:
            num_free.next = depth
            odata.next = 0
            last_line_oh.next = 1
            for i in range(len(next_free)):
                next_free[i].next = 0
                next_avail.next[i] = 1
        else:
            set.next = 0
            clear.next = 0
            if push==1 and pop==1:
                odata.next = idata
            if pop==1 and push==0:
                assert num_free>0
                num_free.next = num_free-1
                odata.next = next_out
                next_avail[i].next = 0
                set.next = 1
            if push==1 and pop==0:
                assert num_free<depth
                num_free.next = num_free+1
    
    iline_sch = select_rr_onehot(next_avail, last_line_oh, next_line_oh,
                                 name=name+".line_sch")
    inl = onehot_to_nr( next_line_oh, next_line )

    @always_comb
    def setaddr():
        raddr.next   = 0
        renable.next = 0
        waddr.next   = 0
        wenable.next = 0
        iline = idata >> memory_width_w
        icol =  idata & ((1<<memory_width_w)-1)
        if pop==1 and push==0:
            raddr.next = next_line
            renable.next = 1
        if push==1 and pop==0:
            raddr.next = iline
            renable.next = 1

    @always_comb
    def setcol():
        pass
#        oline = next_line

    @always_comb
    def setout():
        next_out = next_free[next_line]

    imem = memory_init(
        idata            = wdata, 
        odata            = rdata,
        raddr            = raddr, 
        waddr            = waddr, 
        renable          = renable, 
        wenable          = wenable, 
        soft_reset       = 0, 
        doing_init       = doing_init, 
        clk              = clk, 
        rstn             = rstn, 
        consistency_data = consistency_data, 
        depth            = memory_depth, 
        write_through    = 0, 
        reset_value      = 1, 
        pre_load         = 0, 
        name=name+".mem")

    return instances()


def free_matrix_mem3(
        idata, odata, push, pop, num_free, consistency_check,
        clk, rstn, b_depth=40, fm_width=None, name=""):

    """
    Free matrix circuit block based on the following major instances
    - A 2-port sram memory with latency=3 used as a free matrix
    - A shallow registerbased fifo to hide the latency of the memory 
      read and allow flexibility in the pushing of data into it
    - A shallow cache that contain the 2 latest _potentially_ data 
    altering events (Write or NoWrite) on the memory to hide the latency 
    of previous memory writes 
    - An Availability Vector that points out the free matrix entries 
    where there are free buffer addresses indicated and also provides 
    a capped number of free buffer addresses. AV operations are initiated
    in the first timeslot in the pipeline.
    - Various control logic, level counters, aggregator, deaggregator, 
    inner and outer bypasses

    Each bit in the memory represents if a buffer cell/entry is free 
    encoding is: 
        1 <=> FREE, 
        0 <=> IN_USE 

    Most of the time this is correct but not always. The exceptions 
    to this are:
    0) initialization is still going on 
    1) The cache contains a more up to date state and this is about 
    to be written into the memory
    2) the entry containing the bit was consumed and put into the output 
    pipe (deaggreate, fifo, outmux) and will soon be IN_USE
    3) the corresponding b-address is bypassing the free matrix memory

    Free buffer addresses "b_addr" are pushed into the free block.
    The b_addr is split into two parts; b1_addr (high-index/msb-end) and 
    b0_addr (low-index/lsb-end). The b0_addr part is expanded to a one-hot word
    b0_addr_x that is merged with the associated entry in the free-matrix.
    When possible the entire free matrix entry is extracted (read) 
    and is un-expanded into the b addresses - one by one - and they are
    pushed to the fifo.

    Parameters
        b_depth - buffer depth
        fm_width - free matrix entry/word width
                   only allows 2**<n> argument, it is very fast and 
                   simple to implement division by 2**<n> when using 
                   binary bits        
    """

    print("Instantiated free_matrix_mem3 %s with depth %d" %(name, b_depth), end=' ')

    # default free matrix width
    if fm_width is None:
        fm_width = 32
        print("and default fm_width %d is used" % fm_width)
    else:
        print("and with fm_width %d" % fm_width)

    if fm_width >= b_depth:
        ow = fm_width
        fm_width = 1
        while fm_width*fm_width < b_depth:
            fm_width *= 2
        print("free_mem3: %s fm_width %s was wider than the buffer depth %s. Setting it to the lowest 2^n > sqrt(depth): %s" % (name, ow, b_depth, fm_width))
        
    # check that fm_width is a power of 2
    assert fm_width == 2**(fm_width.bit_length()-1)
    # check that memory will have at least 2 words
    assert fm_width < b_depth


    # Consistency check
    cons_array = Signal(modbv(0)[b_depth:])
    @always(clk.posedge, rstn.negedge)
    def cons_block():
        if rstn == 0:
            cons_array.next = 0
        elif consistency_check==1:
            "synthesis translate_off"
            nfree = 0
            for i in range(len(cons_array)):
                if cons_array[i] == 1:
                    print("%s consistency info: %s non-free" % (name, i))
                    nfree += 1
            if nfree > 0:
                assert False, ("%s Consistency check FAILED! There are %s non-free addresses" % (name, nfree))
            "synthesis translate_on"
        else:
            "synthesis translate_off"
            if pop==1:
                if cons_array[odata] != 0:
                    print("ERROR! Popping non-free addr %s in %s" % (odata, name))
                cons_array.next[odata] = 1
            if push==1:
                if cons_array[idata] != 1: 
                    print("ERROR! Pushing already free addr %s in %s" % (idata, name))
                cons_array.next[idata] = 0
            "synthesis translate_on"
            
    ###
    # free matrix memory
    # fm-entries are not initialized until new free b-addresses are added
    # the available vector registers are initialized though and is used to
    # force fresh entries to be written when corresponding av-value is 0 

    # the latency in number of rising clock edges to process a read
    # operation with the memory used as the free matrix
    FM_LATENCY = 3 # 3 is the only allowed latency value
    DA_FIFO_OF_LATENCY = 1+1+1 # da + fifo + of

    # additional fifo elasticity needed for inner_bypass not to interfere
    # with already initiated extraction
    IB_ELASTICITY = 3 # = FM_LATENCY (?)
    
    b_addr_bits = (b_depth-1).bit_length()
    fm_depth = (b_depth-1)//fm_width + 1
    b1_addr_bits = (fm_depth-1).bit_length()
    b0_addr_bits = b_addr_bits - b1_addr_bits
    b0_addr_x_bits = fm_width
    fm_waddr = Signal(intbv(0)[b1_addr_bits:])
    fm_raddr = copySignal(fm_waddr)
    fm_renable = Signal(intbv(0)[1:])
    fm_wenable = Signal(intbv(0)[1:])
    fm_idata   = Signal(intbv(0)[fm_width:])
    fm_odata   = Signal(intbv(0)[fm_width:])
    push_and_not_pop = Signal(intbv(0)[1:])

    pipes=[]
    push_d = [Signal(intbv(0)[1:0]) for _ in
              range(FM_LATENCY+DA_FIFO_OF_LATENCY+1)]
    pipes.append(pipeline(push, push_d, clk, rstn,
                           name=name+".pipes_push"))
    push_d_num_free = Signal(intbv(0)[1:])

    ###
    # aggregate and extract signals are used in other places
    # need to declare them early

    ae_fifo_part_full = Signal(intbv(0)[1:0])
    ae_extract_req = Signal(intbv(0)[1:0])
    ae_b0_x_write  = Signal(intbv(0)[b0_addr_x_bits:])
    ae_aggregate_b0_x_prio_out = Signal(intbv(0)[b0_addr_x_bits:])
    ae_extract_b0_x_prio_out = Signal(intbv(0)[b0_addr_x_bits:])
    
    # ae control signal delay pipes - depth can possibly be trimmed later
    ae_pipes=[]

    ae_initialize = Signal(intbv()[1:0])
    
    ae_aggregate = Signal(intbv(0)[1:0])
    ae_aggregate_d = [Signal(intbv(0)[1:0]) for _ in range(FM_LATENCY+1)]
    ae_pipes.append(pipeline(ae_aggregate, ae_aggregate_d, clk, rstn,
                           name=name+".ae_pipes_ae_aggregate"))
    ae_extract = Signal(intbv(0)[1:0])
    ae_extract_d = [Signal(intbv(0)[1:0]) for _ in range(FM_LATENCY+1)]
    ae_pipes.append(pipeline(ae_extract, ae_extract_d, clk, rstn,
                           name=name+".ae_pipes_ae_extract"))

    ae_outer_bypass = Signal(intbv(0)[1:0])

    ae_inner_bypass = Signal(intbv(0)[1:0])
    ae_inner_bypass_d = [Signal(intbv(0)[1:0]) for _ in range(FM_LATENCY+1)]
    ae_pipes.append(pipeline(ae_inner_bypass, ae_inner_bypass_d, clk, rstn,
                           name=name+".ae_pipes_ae_inner_bypass"))

    """
    if hwconf.memory_mode == 'inferred':
        consistency_data = [
            Signal(intbv(0)[fm_width-1:]) for _ in range(fm_depth) ]
    else:
        print("Warning: No consistency check for", name, 
              " due to memory mode", hwconf.memory_mode)
        consistency_data = None
    """
    
    consistency_data = None
    
    inst_fm = memory(
        idata = fm_idata, 
        odata = fm_odata,
        raddr = fm_raddr, 
        waddr = fm_waddr, 
        renable = fm_renable, 
        wenable = fm_wenable,  
        clk = clk, 
        rstn = rstn, 
        consistency_data = consistency_data, 
        depth = fm_depth, 
        write_through = 1, 
        input_flops = 1,
        output_flops = 1,  
        name = name + ".fm",
    )

    ###
    # idata delay pipes
    
    idata_d = [Signal(intbv(0)[b_addr_bits:0]) for _ in range(FM_LATENCY+1)]
    pipes.append(pipeline(idata, idata_d, clk, rstn,
                           name=name+".pipes_idata"))

    ###
    # cache fm w-operations (writes or no write) for the latest 2 clock cycles
    ca_payload_bits = fm_width
    ca_tag_bits = b1_addr_bits
    # code is currently designed for CA_DEPTH = 2 ONLY as cache match prio
    # needs to be coded explicitly for synthesis to work
    CA_DEPTH = FM_LATENCY - 1 # 3 - 1 = 2 when mem3 write through is available,
                              # otherwise 3 - 0 = 3
    ca_pointer = Signal(modbv(val=0, min=0, max=CA_DEPTH)) # wrap around!

    ca_write = Signal(intbv(0)[1:])
    ca_write_valid = Signal(intbv(0)[1:])
    ca_write_payload = Signal(intbv(0)[ca_payload_bits:])
    ca_write_tag = Signal(intbv(0)[ca_tag_bits:])

    ca_valid_data = [copySignal(ca_write_valid) for _ in range(CA_DEPTH)]
    ca_tag_data = [copySignal(ca_write_tag) for _ in range(CA_DEPTH)]
    ca_payload_data = [
        Signal(intbv(0)[ca_payload_bits:]) for _ in range(CA_DEPTH)]

    ca_lookup = Signal(intbv(0)[1:])
    ca_lookup_valid = Signal(intbv(0)[1:])
    ca_lookup_tag = Signal(intbv(0)[ca_tag_bits:])
    ca_lookup_hit = Signal(intbv(0)[1:])
    ca_lookup_hit_payload = Signal(intbv(0)[ca_payload_bits:])

    @always_comb
    def combPushDNumFree():
        # do not increase num_free until b-address has propagated
        # through the circuits
        # push_d_num_free.next = push_d[FM_LATENCY+5]
        push_d_num_free.next = push_d[FM_LATENCY+DA_FIFO_OF_LATENCY]

    @always_comb
    def combPushNotPop():
        push_and_not_pop.next = push & ~ pop

    @always_comb
    def combOuterBypass():
        ae_outer_bypass.next = push & pop

    @always(clk.posedge, rstn.negedge)
    def seqCacheData():
        if rstn==0:
            # restart and invalidate cache
            ca_pointer.next = 0 # functionally not needed but easier to debug
            for i in range(CA_DEPTH):
                ca_valid_data[i].next = 0
                ca_tag_data[i].next = 0
                ca_payload_data[i].next = 0
            ca_lookup_hit.next = 0
            ca_lookup_hit_payload.next = 0
        else:
            ca_lookup_hit_payload.next = 0
            for i in range(CA_DEPTH):
                ca_valid_data[i].next = ca_valid_data[i]
                ca_tag_data[i].next = ca_tag_data[i]
                ca_payload_data[i].next = ca_payload_data[i]

            if ca_write==1:
                ca_valid_data[ca_pointer].next = ca_write_valid
                ca_tag_data[ca_pointer].next = ca_write_tag
                ca_payload_data[ca_pointer].next = ca_write_payload

            if ca_lookup==1:
                ca_lookup_hit.next = 0
                #
                ## this is not synthesizable have to unroll this for now!
                #
                #for j in range(ca_pointer, ca_pointer + CA_DEPTH):
                #    if ((ca_valid_data[j%CA_DEPTH] == ca_lookup_valid)
                #        and (ca_tag_data[j%CA_DEPTH] == ca_lookup_tag)
                #    ):
                #        ca_lookup_hit.next = 1
                #        ca_lookup_hit_payload.next = ca_payload_data[
                #            j%CA_DEPTH]
                #
                if ca_pointer == 0:
                   if ((ca_valid_data[0] == ca_lookup_valid)
                        and (ca_tag_data[0] == ca_lookup_tag)
                    ):
                        ca_lookup_hit.next = 1
                        ca_lookup_hit_payload.next = ca_payload_data[0]

                if ((ca_valid_data[1] == ca_lookup_valid)
                    and (ca_tag_data[1] == ca_lookup_tag)
                ):
                    ca_lookup_hit.next = 1
                    ca_lookup_hit_payload.next = ca_payload_data[1]

                if ca_pointer == 1:
                   if ((ca_valid_data[0] == ca_lookup_valid)
                        and (ca_tag_data[0] == ca_lookup_tag)
                    ):
                        ca_lookup_hit.next = 1
                        ca_lookup_hit_payload.next = ca_payload_data[0]
                        
                if ((ca_write==1)
                    and (ca_write_valid==ca_lookup_valid)
                    and (ca_write_tag==ca_lookup_tag)
                ):
                    ca_lookup_hit.next = 1
                    ca_lookup_hit_payload.next = ca_write_payload
                
            ca_pointer.next = ca_pointer + 1

   
    ###
    # deaggregate signals are used in other places
    # need to declare them early

    da_width = fm_width
    da_b1_in = copySignal(fm_raddr)
    da_b0_x_in = copySignal(fm_odata)
    da_b1 = copySignal(da_b1_in)
    da_b0_x = copySignal(da_b0_x_in)
    da_b0_x_next = copySignal(da_b0_x)
    da_en = Signal(intbv(0)[1:])
    da_empty = Signal(intbv(0)[1:])
    da_pop = Signal(intbv(0)[1:])
    da_out = copySignal(idata)

    # da_level range is 0x00 to 0x10 when fm_width is 16
    # in this case add one extra bit for a total of 6 bits
    # to ensure enough bits for correct comparison when
    # deciding if to extract or not below
    da_level = Signal(intbv(0)[max(6, b0_addr_bits+1):]) 

    # to control arithmetic op bit length
    # zero_dummy = Signal(intbv(0)[b0_addr_bits+1+1:]) 
 
    ###
    # fifo signals are used in other places
    # need to declare them early

    # the second fifo in fifo_mem3 needed to be 5 (mem_latency+2) 
    # and need 3 extra to have managable logic for inner bypass
    #fifo_depth = FM_LATENCY + 2 + 3
    fifo_depth = FM_LATENCY + 2 + IB_ELASTICITY
    fifo_idata = copySignal(idata)
    fifo_odata = copySignal(odata)
    fifo_push = Signal(intbv(0)[1:0])
    fifo_push0 = Signal(intbv(0)[1:0])
    fifo_push1 = Signal(intbv(0)[1:0])
    fifo_pop = Signal(intbv(0)[1:0])
    fifo_full = Signal(intbv(0)[1:0])
    fifo_empty = Signal(intbv(0)[1:0])
    fifo_level = Signal(intbv(0)[fifo_depth.bit_length():0])

    # initialization counter
    # starts at 1 and stops at b_depth (0 is default in output flipflop) 
    init_counter = Signal(intbv(0, min=0, max=b_depth+1))

    ###
    # available vector
    # default to zeros when reset
    # contains number of free b-addresses for each fm entry
    # the value of free b-addresses is capped
    # e.g. possible values are {0,1,2,3=<} when AV_WIDTH=2
    # when a fm entry is about to be used the corresponding
    # av-entry is reset to zero and accumulation its free b-addresses
    # is restarted immediately
    
    AV_WIDTH = 2 # only 2 is allowed (FM_LATENCY.bit_length())
    av_depth = fm_depth
    av_addr_bits = (av_depth-1).bit_length()
    av_data = [Signal(intbv(0)[AV_WIDTH:0]) for _ in range(av_depth)]

    # any free b-address in entry
    av_any = [Signal(intbv(0)[1:0]) for _ in range(av_depth)]

    # read capped counter contents at the start of aggregation
    av_address = Signal(intbv(0)[av_addr_bits:])
    av_out = Signal(intbv(0)[AV_WIDTH:]) # capped number of b-addresses in the
                                         # av_address fm entry
    av_out_next = Signal(intbv(0)[AV_WIDTH:])
    
    # to reset capped counter to 0
    av_zero = Signal(intbv(0)[1:])
    av_zero_address = Signal(intbv(0)[av_addr_bits:])

    # to increase capped counter with 1 if <3
    av_inc = Signal(intbv(0)[1:])
    av_inc_address = Signal(intbv(0)[av_addr_bits:])

    # next fm-entry with free b-address, if any, it is the one with
    # highest address
    #
    # status output - there is/are free b-address(es)
    av_free = Signal(intbv(0)[1:])
    # at this free matrix address
    av_free_address =  Signal(intbv(0)[av_addr_bits:])
    # "number of" set bits (b-addresses)
    # for this entry (capped: 0,1,2,3=<)
    av_free_out = Signal(intbv(0)[AV_WIDTH:])

    # av delay pipes - depth can possibly be trimmed later
    av_pipe_depth = FM_LATENCY
    av_pipes=[]
    av_out_d = [Signal(intbv(0)[AV_WIDTH:0]) for _ in range(av_pipe_depth+1)]
    av_pipes.append(pipeline(av_out, av_out_d, clk, rstn,
                           name=name+".av_pipes_av_out"))
    av_free_out_d = [copySignal(av_free_out) for _ in range(av_pipe_depth+1)]
    av_pipes.append(pipeline(av_free_out, av_free_out_d, clk, rstn,
                           name=name+".av_pipes_av_free_out"))
    av_free_address_d = [copySignal(av_free_address)
                         for _ in range(av_pipe_depth+1)]
    av_pipes.append(pipeline(av_free_address, av_free_address_d, clk, rstn,
                           name=name+".av_pipes_av_free_address"))

    @always_comb
    def combAvZeroAddress():
        av_zero_address.next = av_free_address_d[0]

    @always(clk.posedge, rstn.negedge)
    def seqAvailableVectorData():
        if rstn==0:
            for i in range(av_depth):
                av_data[i].next = 0
        else:
            for i in range(av_depth):
                av_data[i].next = av_data[i]

            if ((av_inc == 1)
                and (av_zero == 1)
                and (av_inc_address == av_zero_address)
            ):
                # handle case were zero and inc addresses are identical
                "lint_waive RANGE_OFLOW: this number of bits needed"
                av_data[av_inc_address].next = 1
            else:
                "lint_waive RANGE_OFLOW: this number of bits needed"
                if (av_inc==1) and (av_data[av_inc_address]<3):
                    # adds one more b-address to this free matrix entry if <3
                    "lint_waive RANGE_OFLOW: this number of bits needed"
                    av_data[av_inc_address].next = 1 + av_data[av_inc_address]
                if av_zero==1:
                    # contents of this fm-entry is fed to deaggregate
                    "lint_waive RANGE_OFLOW: this number of bits needed"
                    av_data[av_zero_address].next = 0 

    @always_comb
    def combAvAddress():
        av_address.next = idata_d[0][:b0_addr_bits]
        
    @always_comb
    def combAvOut():
        "lint_waive RANGE_OFLOW: this number of bits needed"
        av_out.next = av_data[av_address]
        
    @always_comb
    def combAvAny():
        for i in range(av_depth):
                av_any[i].next = av_data[i][1] | av_data[i][0]
                
    # last av_address that indicates free buffer cells
    # logic depth of this one might get tricky
    @always_comb
    def combAvFreeAddress():
        av_free.next = 0
        av_free_address.next = 0
        for i in range(av_depth):
            if av_any[i]==1:
                av_free.next = 1
                av_free_address.next = i
                
    @always_comb
    def combAvFreeOut():
        if ae_inner_bypass_d[0]==1:
            av_free_out.next = 0
        elif ae_extract_d[0]==1:
            "lint_waive RANGE_OFLOW: this number of bits needed"
            av_free_out.next = av_data[av_free_address]
        else:
            av_free_out.next = 0
              
    ###
    # The (b-address) aggregation and extraction block
    # 
    # This block manages the inflow and outflow of b-addresses.
    #
    # Aggregation referes to adding a free b-address to the free matrix.
    # Extraction refers to pulling the current _set_ of free b-addresses
    # of the next-in line fm-entry in the free matrix (unless there is a
    # newer version in the cache that is used instead) and pushing this
    # to the deaggregator. This fm-entry is pointed out by the
    # availability vector.
    #  

  
    @always_comb
    def combAeExtractReq():
        # predict possibility to extract from memory and put in
        # deaggregation and then fifo
        # don't edit unless being very confident

        # move from fm to da when something to move and ensure
        # _future_ space in deaggregation to push into

        if (
            # Check if any space in fifo to move to
            # number of bits in this comparison is controlled by da_level
            # Note that one of the av_free_out_d[i] and ae_inner_bypass_d[i]
            # sharing identical index value is always zero
            (fifo_depth
             +fifo_pop
             +1) > (da_level
                    + fifo_level
                    + av_free_out_d[1]
                    + av_free_out_d[2]
                    + av_free_out_d[3]
                    + ae_inner_bypass_d[1]
                    + ae_inner_bypass_d[2]
                    + ae_inner_bypass_d[3]
             )
        ) and (
            # There must be time to deaggregate any
            # previous b0_x word already in the fm read pipe
            # when also considering initiated inner bypasses
            av_free_out_d[1] < 2
        ) and (
            # or the one before that
            # (3 represents >=3)
            av_free_out_d[2] < (3 - ae_inner_bypass_d[1])
        ) and (
            # or the one before that
            av_free_out_d[3] < (
                3 - ae_inner_bypass_d[2] - ae_inner_bypass_d[1])
        ) and (
            # limited number of clock cycles available to empty deaggregate
            # all da b-addresses must be popped when new data is loaded
            # figure out how much that can be transferred
            # to fifo before this possible new fm-entry would arrive
            (da_level
             + ae_inner_bypass_d[1]
             + ae_inner_bypass_d[2]
             + ae_inner_bypass_d[3]
            ) < (4 + da_pop)
        ) and (
            # there must be data to move
            av_free==1
        ):
            # request an extraction of an entry from free matrix memory
            ae_extract_req.next = 1
        else:
            ae_extract_req.next = 0
        
    @always_comb
    def combAeInitialization():
        # is initialization still going on?
        if init_counter != b_depth:
            ae_initialize.next = 1
        else:
            ae_initialize.next = 0

    @always_comb
    def combAeFifoPartiallyFull():
        # is fifo more than half-full-ish?
        if (fifo_level<fifo_depth-IB_ELASTICITY):
            ae_fifo_part_full.next = 0
        else:
            ae_fifo_part_full.next = 1

    @always_comb
    def combAeControl():
        # no difference between initialization and after it
            
        # do inner bypass unless fifo is
        # or might _become_ full
        ae_inner_bypass.next = push_and_not_pop & ~ae_fifo_part_full

        # do aggregate? (when fifo is or might _become_ full)
        ae_aggregate.next = push_and_not_pop & ae_fifo_part_full

        # do extract? 
        ae_extract.next = ae_extract_req & ~ push_and_not_pop 

    @always_comb
    def combAeAggregatePrioOutput():
        # select the right output data
        if av_out_d[FM_LATENCY]==0:
            # this one applies mainly to aggregation and not extraction
            # this entry was recently extracted and one shall restart
            # aggregation from 0
            # and ignore the memory and cache, if any, contents 
            ae_aggregate_b0_x_prio_out.next = 0
        elif ca_lookup_hit==1:
            ae_aggregate_b0_x_prio_out.next = ca_lookup_hit_payload
        else:
            ae_aggregate_b0_x_prio_out.next = fm_odata

    @always_comb
    def combAeExtractPrioOutput():
        # select the right output data
        if ca_lookup_hit==1:
            ae_extract_b0_x_prio_out.next = ca_lookup_hit_payload
        else:
            ae_extract_b0_x_prio_out.next = fm_odata

    @always_comb
    def combAeFreeMatrixReadInitiate():
        if ae_aggregate_d[0]==1:
            # initiate read of the corresponding fm-entry to the
            # incoming b-address
            fm_renable.next = 1
            fm_raddr.next = idata_d[0][:b0_addr_bits]
        elif ae_extract_d[0]==1:
            # initiate read of the next-in-line fm-entry
            # and initate zeroing of the corresponding av entry
            fm_renable.next = 1
            fm_raddr.next = av_free_address_d[0]
        else:
            fm_renable.next = 0
            fm_raddr.next = idata_d[0][:b0_addr_bits]

    @always_comb
    def combAeAvailableZero():
        if ae_aggregate_d[0]==1:
            # do nothing
            av_zero.next = 0
        elif ae_extract_d[0]==1:
            # and initate zeroing of the corresponding av entry
            av_zero.next = 1
        else:
            av_zero.next = 0

    @always_comb
    def combAeFreeMatrixCacheWrite():
        ae_b0_x_write.next = (
            #this one appear to work bitlength-wise
            ae_aggregate_b0_x_prio_out
            | 2**idata_d[FM_LATENCY][b0_addr_bits:]
        )

    @always_comb
    def combAeFreeMatrixCacheWriteData():
        fm_waddr.next = idata_d[FM_LATENCY][:b0_addr_bits]
        fm_idata.next = ae_b0_x_write
        ca_write_tag.next = idata_d[FM_LATENCY][:b0_addr_bits]
        ca_write_payload.next = ae_b0_x_write
        ca_write.next = 1 #always store latest ops and nops

        if ae_aggregate_d[FM_LATENCY]==1:
            # initiate write the corresponding fm-entry of the
            # incoming b-address
            fm_wenable.next = 1
            ca_write_valid.next = 1
        else:
            # a write is not needed at extraction
            # since availability vector was set to 0
            fm_wenable.next = 0
            ca_write_valid.next = 0

    @always_comb
    def combAeAvailabilityVectorInc():
        av_inc_address.next = idata_d[0][:b0_addr_bits]
        av_inc.next = ae_aggregate_d[0]

    @always_comb
    def combAeCache():
        ca_lookup_tag.next = 0
        ca_lookup_valid.next = 0
        ca_lookup.next = 0
        if ae_aggregate_d[FM_LATENCY-1]==1:
            ca_lookup.next = 1
            ca_lookup_valid.next = 1
            ca_lookup_tag.next = idata_d[FM_LATENCY-1][:b0_addr_bits]
        elif ae_extract_d[FM_LATENCY-1]==1:
            ca_lookup.next = 1
            ca_lookup_valid.next = 1
            ca_lookup_tag.next = av_free_address_d[FM_LATENCY-1]

    @always_comb
    def combAeDaEnable():
        # take care of output of free matrix memory/cache entry
        da_en.next = ae_extract_d[FM_LATENCY]

    @always_comb
    def combAddressEntry():
        da_b1_in.next = av_free_address_d[FM_LATENCY]
        da_b0_x_in.next = ae_extract_b0_x_prio_out

    # Deaggregate transforms an fm-entry (with >0 free b-addresses indicated)
    # into b-addresses that is transferred into the fifo when there is space

    @always(clk.posedge, rstn.negedge)
    def seqDeaggregate():
        if rstn == 0:
            da_b1.next = 0
            da_b0_x.next = 0
        else:
            da_b1.next = da_b1
            da_b0_x.next = da_b0_x
            if da_en == 1:
                # new b1 and b0_x input 
                da_b1.next = da_b1_in
                da_b0_x.next = da_b0_x_in
            elif da_pop == 1:
                # one b-address was pop:ed and entry shall be updated
                da_b0_x.next = da_b0_x_next

    @always_comb
    def combDeaggregateOutLevelEmpty():
        da_level.next = 0
        da_empty.next = 1
        da_out.next[b0_addr_bits:] = 0
        da_out.next[:b0_addr_bits] = da_b1
        j=0
        for i in range(da_width):
            if da_b0_x[i] == 1:
                j += 1
                da_out.next[b0_addr_bits:] = i
                da_empty.next = 0
                
        "lint_waive UNEQUAL_LEN: j <= i < da_width"        
        da_level.next = j

    @always_comb
    def combDeaggregatePurged():
        # problem with automatic bitlength for verilog 2**n expression
        # and larger exponents values (n) compared to n bitlength
        # make the following expression not work
        # da_b0_x_next.next = da_b0_x & ~ 2**da_out[b0_addr_bits:]

        # uses this one instead that appear to work better
        da_b0_x_next.next = da_b0_x & ~ (1 << da_out[b0_addr_bits:])

    # output flipflop with enable

    of_idata = copySignal(odata)
    of_odata = copySignal(odata)
    of_enable = Signal(intbv(0)[1:])
    of_occupied = Signal(intbv(1)[1:])

    @always_comb
    def combFifoInputPush():
        # ae_inner_bypass_d[FM_LATENCY]
        da_pop.next = 0
        fifo_push0.next = 1
        fifo_push1.next = 0
        if ae_inner_bypass_d[FM_LATENCY] == 0:
            fifo_push0.next = 0
            if (da_empty == 0) and (fifo_full == 0):
                da_pop.next = 1
                fifo_push1.next = 1
            else:
                da_pop.next = 0
                fifo_push1.next = 0

    @always_comb
    def combFifoInputMux():
        if fifo_push0==1:
            fifo_idata.next = idata_d[FM_LATENCY]
        else:
            fifo_idata.next = da_out

    @always_comb
    def combFifoPush():
        fifo_push.next = fifo_push0 | fifo_push1

    # fifo in output pipe to hide latency

    inst_fifo = fifo_signal(fifo_idata, fifo_odata, fifo_push, fifo_pop,
                            fifo_full, fifo_empty, fifo_level, clk, rstn,
                            clear=0, depth=fifo_depth,
                            memoryMode='ff', name=name + 'fifo')

    # fifo to output flip-flop pop transfer
    @always_comb
    def combFifoPop(): 
        if (
                (ae_initialize==0
                 and pop==1
                 and push==0
                )
                or (of_occupied==0)
        ) and (
            fifo_empty==0
        ):
            fifo_pop.next = 1
        else:
            fifo_pop.next = 0

    @always(clk.posedge, rstn.negedge)
    def seqInitializationCounter():
        if rstn==0:
            init_counter.next = 1
        else:
            init_counter.next = init_counter
            if ae_initialize==1:
                # outer bypass is allowed during init
                if (pop == 1) and (ae_outer_bypass == 0):
                    init_counter.next = init_counter + 1

    # output flipflop with enable 
    inst_outflop   = flop_e(
        of_idata, of_odata, of_enable, clk, rstn, reset_value=0,
        name=name+".outflop")

    # output flip-flop occupied
    @always(clk.posedge, rstn.negedge)
    def seqOutputFlipFlopOccupied():
        if rstn==0:
            of_occupied.next = 1
        else:
            of_occupied.next = of_occupied
            if of_enable==1:
                of_occupied.next = 1
            else:
                if pop==1:
                    of_occupied.next = 0

                    
    @always_comb
    def combOutputFlipFlopEnable():
        if ae_initialize==0:
            if ae_outer_bypass==1:
                of_enable.next = 1
            else:
                of_enable.next = fifo_pop
        else:
            of_enable.next = pop

    @always_comb
    def combOutputFlipFlopInput():
        # using indirect test of the init_counter value as in:
        # "if ae_initialize==0:" is not explicit enough to automatically
        # limit the max value of init_counter when assigning it to
        # of_idata below, so one have to write the test very verbatim
        # for python interpreter to be happy:
        
        of_idata.next = 0
        if init_counter==b_depth:
            # initialization is done
            if pop==1:
                if push==1:
                    of_idata.next = idata
                elif fifo_empty==0:
                    of_idata.next = fifo_odata
            else:
                if fifo_pop==1:
                    of_idata.next = fifo_odata
        else:
            # initialization is going on
            # outer bypass is allowed during init
            if ae_outer_bypass==1:
                of_idata.next = idata
            else:
                of_idata.next = init_counter[b_addr_bits:]  

    @always_comb
    def combOutputFlipFlopOutput():
        odata.next = of_odata
            
    # num_free
    @always(clk.posedge, rstn.negedge)
    def seqNumFree():
        if rstn==0:
            num_free.next = b_depth
        else:
            num_free.next = num_free
            if (pop==1) and (push==0):
                "synthesis translate_off"
                if num_free==0:
                    print("ERROR! Popping empty for %s" % name)
                "synthesis translate_on"   
            if (pop==1) and (push_d_num_free==0):
                num_free.next = num_free-1
            if (push==1) and (pop==0):
                "synthesis translate_off"
                if num_free==b_depth:
                    print("ERROR! Pushing full for %s" % name)
                "synthesis translate_on"   
            if (push_d_num_free==1) and (pop==0):
                num_free.next = num_free+1

    return instances()
