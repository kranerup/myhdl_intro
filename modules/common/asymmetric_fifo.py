from myhdl import *
from .Common import pass_through, sliceSignal, signalType, modInc, copySignal
from .memory import *
import math
"""
File status:
The asymetric_fifo was used in sp and ps, but it is no longer used
anywhere. The timing sucks.
"""

def cntup_base(ibase, irest, obase, orest, diff, base=8):
    if diff.max > base:
        print("ERROR! cntup_base cannot be incremented by more than the base at a time")
        assert False
    @always_comb
    def basec():
        if diff+irest > base:
            obase.next = ibase+1
            orest.next = irest-base+diff
        else:
            obase.next = ibase
            orest.next = irest+diff
    return instances()


def asymmetric_fifo(idata,odata,push,pop,full,empty,olevel,clk,rstn,
                    could_become_full=None, margin=1,
                    ivalid_bytes=None,ifirst=None,ilast=None,
                    ovalid_bytes=None,ofirst=None,olast=None,
                    depth=4,memoryMode='ff',name=""):
    """
    A FIFO where the input and output port widths differ. 

    The valid_bytes, first and last ports are optional


    TODO: Clean up the naming
    TODO: Most of the first, last and valid_bytes registers can be otimized away by using head and tail counters separated into div and mod for input and output. Perhaps a similar length counter is needed as well. (This would also cut the logic depth)
    TODO: Register files instead of flops, when possible
    """

    if signalType(idata):
        afifo_sig = asymmetric_fifo_signal(idata, odata, push, pop, full, empty, olevel, clk, rstn,
                                           could_become_full, margin,
                                           ivalid_bytes, ifirst, ilast,
                                           ovalid_bytes, ofirst, olast,
                                           depth, memoryMode, name)
    else:
        print("ERROR! Unsupported type for fifo "+name+":", type(idata).__name__)
        exit()
    return instances()

    
def asymmetric_fifo_signal(idata,odata,push,pop,full,empty,olevel,clk,rstn,
                           could_become_full, margin,
                           ivalid_bytes,ifirst,ilast,
                           ovalid_bytes,ofirst,olast,
                           depth,memoryMode='ff',name=None):

    # In the cnt_mode we use first, last and valid_bytes ports. 
    # In cnt_mode not all bytes in a word need to be valid.
    cnt_mode = False
    if ivalid_bytes != None:
        cnt_mode = True

    # In could_become_full_mode we output an could_become_full flag which is 
    # set high when the number of free bytes is less than "margin" output words
    could_become_full_mode = False
    if could_become_full != None:
        could_become_full_mode = True
    
    iw = len(idata)
    ow = len(odata)
    if iw<ow:
        idepth = depth*ow//iw
        odepth = depth
    elif ow<iw:
        idepth = depth
        odepth = depth*iw//ow
    else:
        idepth = depth
        odepth = depth
        print("Warning! Asymmetric_fifo instatiated as symmetric iw = ", iw, "ow = ", ow, "Probably less than optimal.") 

    gcd = math.gcd(iw, ow)

    ichunks = iw//gcd
    ochunks = ow//gcd
    word = ichunks*ochunks//math.gcd(ichunks, ochunks)

    bits = depth*word*gcd
    gdepth = bits//gcd

    ibytes = iw//8
    obytes = ow//8
    gbytes = gcd//8
    

#    print "asymmetric_fifo", name, "instantiated"
#    print "  iw     ", iw
#    print "  ow     ", ow
#    print "  gcd    ", gcd
#    print "  odepth ", odepth  
#    print "  idepth ", idepth 
#    print "  gdepth ", gdepth 
#    print "  ichunks", ichunks 
#    print "  ochunks", ochunks
#    print "  obytes ", obytes  
#    print "  ibytes ", ibytes 
#    print "  gbytes ", gbytes 
#    print "  word   ", word
#   
    def splitNumber(val, out, depth):
        nr = len(out)
        @always_comb
        def sn():
            for i in range(nr):
                if val > depth*i:
                    out[i].next = depth
                else:
                    if val - depth*i < 0:
                        out[i].next = 0
                    else:
                        out[i].next = val - depth*i
        return instances()

    glevel = Signal(intbv(0, min=0, max=gdepth+1))

    # Head and tail counters in input and output base
    head_base_o = Signal(intbv(0, min=0, max=gdepth//ochunks))
    tail_base_i = Signal(intbv(0, min=0, max=gdepth//ichunks))

    head_base_g = Signal(intbv(0, min=0, max=gdepth))
    tail_base_g = Signal(intbv(0, min=0, max=gdepth))

    head_base_w = Signal(intbv(0, min=0, max=gdepth//word))
    tail_base_w = Signal(intbv(0, min=0, max=gdepth//word))
    head_rest_w = Signal(intbv(0, min=0, max=gdepth//word))
    tail_rest_w = Signal(intbv(0, min=0, max=gdepth//word))

    # Head and tail counters in gcd (Greatest Common Denominator)
    h_word_cnt = Signal(intbv(0, min=0, max=gdepth))
    h_ofl_cnt  = Signal(intbv(0, min=0, max=gdepth))
    h_cnt = Signal(intbv(0, min=0, max=gdepth))
    t_word_cnt = Signal(intbv(0, min=0, max=gdepth))
    t_ofl_cnt  = Signal(intbv(0, min=0, max=gdepth))
    t_cnt = Signal(intbv(0, min=0, max=gdepth))
    @always_comb
    def set_t_cnt():
        t_cnt.next = t_word_cnt + t_ofl_cnt
    @always_comb
    def set_h_cnt():
        h_cnt.next = h_word_cnt + h_ofl_cnt
    
    if cnt_mode:
        array_valid_bytes = [Signal(intbv(0, min=0, max=gbytes+1)) for _ in range(gdepth)]
        array_first = [ Signal(intbv(0)[1:0])                      for _ in range(gdepth) ]
        array_last  = [ Signal(intbv(0)[1:0])                      for _ in range(gdepth) ]
        byte_ofl = Signal(intbv(0, min=0, max=obytes+ibytes+1))

    if memoryMode=='ff':
        data    = [Signal(intbv(0)[gcd:0]) for _ in range(gdepth)]
    else:
        print("ERROR! Unsupported memoryMode for fifo "+name+":", memoryMode)
        exit()

    # Set the could_become_full flag
    if could_become_full_mode:
        margin_level = gdepth - margin*ichunks
        @always_comb
        def setSoon():
            if glevel >= margin_level or (glevel >= gdepth - word):
                could_become_full.next = 1
            else:
                could_become_full.next = 0

    @always_comb
    def setFull():
        if gdepth-glevel < ichunks:
            full.next = 1
        else:
            full.next = 0

    @always_comb
    def setEmpty():
        if glevel < ochunks:
            empty.next = 1
        else:
            empty.next = 0

    output_chunk = [Signal(intbv(0)[gcd:]) for _ in range(ochunks)]

    @always_comb
    def drivechunk():
        for i in range(ochunks):
            output_chunk[i].next = data[h_cnt+i]

#    output_flat = output_chunk[0]
    if len(output_chunk)<2:
        output_flat = output_chunk[0]
    else:
        output_flat = ConcatSignal(*reversed(output_chunk))

    out_inst = pass_through(output_flat, odata, name=name+".od")

    @always(clk.posedge, rstn.negedge)
    def setwotail():
        if rstn==0:
            tail_base_i.next = 0
            t_word_cnt.next = 0
            t_ofl_cnt.next = 0
        else:
            if push==1:
                if full==1:
                    if __debug__:
                        print("ERROR pushing to full FIFO "+name)
                    assert False
                else:
                    ##### << BASE
                    if tail_base_i + 1 < tail_base_i.max:
                        tail_base_i.next = tail_base_i + 1
                    else:
                        tail_base_i.next = 0
                    ##### >> BASE
                    if ilast==0:
                        if t_ofl_cnt + ichunks >= word:
                            t_ofl_cnt.next = t_ofl_cnt + ichunks - word
                            if t_word_cnt + word == gdepth:
                                t_word_cnt.next = 0
                            else:
                                t_word_cnt.next = t_word_cnt + word
                        else:
                            t_ofl_cnt.next = t_ofl_cnt + ichunks
                    else:
                        t_ofl_cnt.next = 0
                        if t_word_cnt == gdepth - word:
                            t_word_cnt.next = 0
                        else:
                            if t_cnt+ichunks > t_word_cnt+word:
                                t_word_cnt.next = t_word_cnt + 2*word
                            else:
                                t_word_cnt.next = t_word_cnt + word

    @always(clk.posedge, rstn.negedge)
    def setwoHead():
        if rstn==0:
            head_base_o.next = 0
            h_word_cnt.next = 0
            h_ofl_cnt.next = 0
        else:
            if pop==1:
                if empty==0:
                    #### << BASE
                    if head_base_o + 1 < head_base_o.max:
                        head_base_o.next = head_base_o + 1
                    else:
                        head_base_o.next = 0
                    #### >> BASE
                    if olast==0:
                        if h_ofl_cnt + ochunks >= word:
                            h_ofl_cnt.next = h_ofl_cnt + ochunks - word
                            if h_word_cnt + word == gdepth:
                                h_word_cnt.next = 0
                            else:
                                h_word_cnt.next = h_word_cnt + word
                        else:
                            h_ofl_cnt.next = h_ofl_cnt + ochunks
                    else:
                        h_ofl_cnt.next = 0
                        if h_word_cnt == gdepth - word:
                            h_word_cnt.next = 0
                        else:
                            if h_cnt+ochunks > h_word_cnt+word:
                                h_word_cnt.next = h_word_cnt + 2*word
                            else:
                                h_word_cnt.next = h_word_cnt + word

                    
    # BEGIN --------  cnt_mode -----------
    if cnt_mode:
        @always(clk.posedge, rstn.negedge)
        def setvalid():
            if rstn==0:
                for i in range(gdepth):
                    array_valid_bytes[i].next = 0
                    array_first[i].next = 0 
                    array_last[i].next = 0 
            else:
                val_list   = [ intbv(0, min=0, max=gbytes+1) for _ in range(ichunks)]
                first_list = [ intbv(0)[1:0]               for _ in range(ichunks)]
                last_list  = [ intbv(0)[1:0]               for _ in range(ichunks)]
                last_valid_chunk = intbv(0)[1:0]
                valid_byte_cnt = 0
                for i in range(ichunks):
                    valid_byte_cnt = valid_byte_cnt + gbytes
                    if valid_byte_cnt >= ivalid_bytes and valid_byte_cnt + gbytes > valid_byte_cnt:
                        last_valid_chunk[:] = 1
                    else:
                        last_valid_chunk[:] = 0
#                    print gbytes, "i", i
                    if ivalid_bytes > gbytes*(i+1):
#                        print gbytes, "  ", ivalid_bytes, ">", gbytes*(i+1), ": setting", gbytes 
                        val_list[i][:] = gbytes
                    else:
#                        print gbytes, "  ", ivalid_bytes, "<=", gbytes*i
                        if ivalid_bytes - gbytes*i < 0:
#                            print gbytes, "    ", ivalid_bytes, "-", gbytes*i, "< 0 : setting 0"
                            val_list[i][:] = 0
                        else:
#                            print gbytes, "    ", ivalid_bytes, "-", gbytes*i, ">= 0 : setting", ivalid_bytes - gbytes*i
                            val_list[i][:] = ivalid_bytes - gbytes*i
                    if i == 0:
                        first_list[i][:] = ifirst
                    else:
                        first_list[i][:] = 0
                    if last_valid_chunk == 1:
                        last_list[i][:] = ilast
                    else:
                        last_list[i][:] = 0
                if push==1:
                    if full==1:
                        print("ERROR! Pushing to full fifo", name)
                        assert False
                    last_ptr = t_cnt + ichunks-1 
                    for i in range(gdepth):
                        list_index = 0
                        if i >= t_cnt:
                            list_index = i-t_cnt
                        not_wrap = 1 
                        if t_cnt+ichunks > gdepth and i < t_cnt+ichunks - gdepth:
                            not_wrap = 0
                        next_border = t_word_cnt + word
                        if t_ofl_cnt + ichunks > word:
                            next_border = t_word_cnt + 2*word
                        if ilast:
                            if (i>last_ptr and i < next_border) or (not_wrap==0 and i < last_ptr):
                                data[i].next        = 0
                                array_valid_bytes[i].next = 0
                                array_first[i].next       = 0
                                array_last[i].next        = 0
                        if (i >= t_cnt and i < t_cnt+ichunks) or (not_wrap==0):
                            data[i].next        = ilist[      list_index ]
                            array_valid_bytes[i].next = val_list[   list_index ]
                            array_first[i].next       = first_list[ list_index ]
                            array_last[i].next        = last_list[  list_index ]
                                    
                        
        @always_comb
        def drivefirst():
            found = intbv(0)[1:0]
            for i in range(gdepth):
                if i >= h_cnt and i < h_cnt+ochunks:
                    if array_first[i]:
                        found[:] = 1
            if empty==0:
                ofirst.next = found
            else:
                ofirst.next = 0
        @always_comb
        def drivelast():
            found = intbv(0)[1:0]
            for i in range(gdepth):
                if i >= h_cnt and i < h_cnt+ochunks:
                    if array_last[i]:
                        found[:] = 1
            if empty==0:
                olast.next = found
            else:
                olast.next = 0

        valid_sum_slice = [ Signal(intbv(0, min=0, max=gbytes+1)) for _ in range(ochunks) ] 
        @always_comb
        def valslice():
            index = 0
            temp = [ intbv(0, min=0, max=gbytes+1) for _ in range(ochunks) ]
            for k in range(ochunks):
                temp[k][:] = 0
            for i in range(gdepth):
                if i >= h_cnt and i < h_cnt+ochunks:
                    temp[index][:] = array_valid_bytes[i]
                    index = index + 1
            for j in range(ochunks):
                valid_sum_slice[j].next = temp[j] 

        valid_sum = copySignal(ovalid_bytes)
        oval_width = len(ovalid_bytes)
        @always_comb
        def valsum():
            temp = intbv(0)[oval_width:]
            for i in range(ochunks):
                temp[:] = temp + valid_sum_slice[i] 
            valid_sum.next = temp
            

        @always_comb
        def driveval():
            if empty==0:
                ovalid_bytes.next = valid_sum
            else:
                ovalid_bytes.next = 0
                
    # END --------  cnt_mode -----------
                

                        
    last_glevel = Signal(intbv(0, min=0, max=gdepth+1))
    lt  =  Signal(intbv(0, min=0, max=gdepth))
    lh  =  Signal(intbv(0, min=0, max=gdepth))
    @always_comb
    def driveglevel():
        td = t_cnt - lt
        hd = h_cnt - lh
        if h_cnt < lh:
            hd = hd + gdepth
        if t_cnt < lt:
            td = td + gdepth
        glevel.next = last_glevel + td - hd

    @always(clk.posedge, rstn.negedge)
    def glevelcount():
        if rstn==0:
            last_glevel.next = 0
            lt.next = 0
            lh.next = 0
        else:
            last_glevel.next = glevel
            lt.next = t_cnt
            lh.next = h_cnt
            

    ilist    = [Signal(intbv(0)[gcd:])             for _ in range(ichunks)]
    slice_inst = sliceSignal(idata, *ilist)

    return instances()

