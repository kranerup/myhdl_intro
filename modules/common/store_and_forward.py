from myhdl import *
from modules.common.Common import pass_through, pipeline, flop, flop_e, zext, listOfSignalsType
from .memory import memory
from .free import free
from .fifo import fifo
"""
File status: The store_and_forward block is not meant to be used
anywhere. It was the inititial packet-through trial it is just kept as
a DUT to test the packet interfaces when new features are added.
"""


def store_and_forward(idata, ivalidBytes, ifirst, ilast,
                      odata, ovalidBytes, ofirst, olast, clk, rstn, depth=4):
    if listOfSignalsType(idata):
#       print "idata", len(idata), "ivalidBytes", len(ivalidBytes), "ifirst", len(ifirst), "ilast", len(ilast)
#       print "odata", len(odata), "ovalidBytes", len(ovalidBytes), "ofirst", len(ofirst), "olast", len(olast)
        iew = []
        for i in range(len(idata)):
            iew.append( 
                store_and_forward_expensive_wire(
                    idata[i], ivalidBytes[i], ifirst[i], ilast[i],
                    odata[i], ovalidBytes[i], ofirst[i], olast[i], clk, rstn, depth=depth)
                )
    else:
        iew = store_and_forward_expensive_wire(
            idata, ivalidBytes, ifirst, ilast,
            odata, ovalidBytes, ofirst, olast, clk, rstn, depth=depth)
    return instances()


def store_and_forward_expensive_wire(idata, ivalidBytes, ifirst, ilast,
                      odata, ovalidBytes, ofirst, olast, clk, rstn, depth=4):

    pbuff_width = len(idata)
    bytes_per_chunk = len(idata)//8
    temp = Signal(intbv(0, min=0, max=depth))
    # We need the width because they are combinatorical, so they cannot be defined using a range
    pbuff_addr_width = len(temp)
    clink_addr_width = pbuff_addr_width

    # Keep track of the unused space in the packet buffer
    free_in       = Signal(intbv(0, min=0, max=depth))   
    free_out      = Signal(intbv(0, min=0, max=depth))   
    free_push     = Signal(intbv(0)[1:0])                  
    next_free_pop = Signal(intbv(0)[1:0])                  
    free_avail    = Signal(intbv(0, min=0, max=depth+1)) 
    consistency_check = Signal(intbv(0)[1:0])                  

    free_pop        = next_free_pop

    ifree = free(
        free_in, 
        free_out, 
        free_push, 
        free_pop,
        free_avail, 
        consistency_check,
        clk, rstn, depth=depth, mode='lifo', name="free")

    # The packet buffer
    pbuff_out   = Signal(intbv(0)[ pbuff_width: ])     
    pbuff_raddr = Signal(intbv(0)[pbuff_addr_width:])                   
    pbuff_re    = Signal(intbv(0)[1:0])                   

    pbuff_in    = idata
    pbuff_waddr = free_out       
    pbuff_we    = next_free_pop
    last_valid_free      = Signal(intbv(0)[ pbuff_addr_width: ])
    valid_free_d    = [Signal(intbv(0)[ pbuff_addr_width: ]) for _ in range(3)]
    valid_free_d_ff = pipeline(free_out, valid_free_d, clk, rstn)


    pbuff = memory(
        pbuff_in, 
        pbuff_out, 
        pbuff_raddr, 
        pbuff_waddr, 
        pbuff_re,
        pbuff_we,
        clk, rstn, depth=depth, name="buff_mem") 

    # The packet link fifo
    pfifo_width = clink_addr_width
    pfifo_depth = 10
    pfifo_in    = Signal(intbv(0)[ pfifo_width: ])   
    pfifo_out   = Signal(intbv(0)[ pfifo_width: ])     
    pfifo_push  = Signal(intbv(0)[1:0])                   
    pfifo_pop   = Signal(intbv(0)[1:0])                  
    pfifo_full  = Signal(intbv(0)[1:0])                  
    pfifo_empty = Signal(intbv(0)[1:0])                  
    pfifo_level = Signal(intbv(0, min=0, max=pfifo_depth+1))                   

    pfifo = fifo(
        idata   = pfifo_in, 
        odata   = pfifo_out, 
        push    = pfifo_push, 
        pop     = pfifo_pop, 
        full    = pfifo_full,
        empty   = pfifo_empty,
        level   = pfifo_level,
        clk     = clk,
        rstn    = rstn,
        depth   = pfifo_depth)

    # The cell link memory
    valid_pbuff_last       =  Signal(intbv(0)[1:0])
    clink_ptr_in  = Signal(intbv(0, min=0, max=max(depth, len(idata)//8+1)))
    clink_eop_in  = Signal(intbv(0)[1:0])
    clink_ptr_out = Signal(intbv(0, min=0, max=max(depth, len(idata)//8+1)))
    clink_eop_out = Signal(intbv(0)[1:0])
    clink_eop_in = valid_pbuff_last
    clink_in    = [clink_ptr_in,  clink_eop_in ]  
    clink_out   = [clink_ptr_out, clink_eop_out]  
    clink_raddr = Signal(intbv(0)[clink_addr_width:])
#    clink_waddr = Signal(intbv(0)[clink_addr_width:])                  
    clink_re    = Signal(intbv(0)[1:0])                  
    clink_re_d  = [ Signal(intbv(0)[1:0]) for _ in range(3) ]
    clink_re_p  = pipeline(clink_re, clink_re_d, clk, rstn)
    clink_we    = Signal(intbv(0)[1:0])                  
    clink_addr_width = len(clink_raddr)
    clink_ptr_width  = len(clink_ptr_in)

    clink_eop_valid = Signal(intbv(0)[1:0])
    

    current_head  = Signal(intbv(0, min=0, max=depth))
    current_chunk = Signal(intbv(0, min=0, max=depth)) 
                
    @always_comb
    def pop():
        next_free_pop.next = False
        if ivalidBytes > 0 and free_avail > 0:
            next_free_pop.next = 1 

    valid_pbuff_waddr      =  Signal(intbv(0)[pbuff_addr_width:])
    valid_pbuff_first       =  Signal(intbv(0)[1:0])
    valid_ivalidBytes      =  Signal(intbv(0)[len(ivalidBytes):0])
    last_valid_pbuff_waddr =  Signal(intbv(0)[pbuff_addr_width:])
    last_valid_pbuff_waddr_ff = flop_e([pbuff_waddr, ilast, ifirst, ivalidBytes], [last_valid_pbuff_waddr, valid_pbuff_last, valid_pbuff_first, valid_ivalidBytes], pbuff_we, clk, rstn)
    @always_comb
    def lvpbwa():
        if pbuff_we==1:
            valid_pbuff_waddr.next = pbuff_waddr
        else:
            valid_pbuff_waddr.next = last_valid_pbuff_waddr
            
    @always_comb
    def setptr():
        if valid_pbuff_last==1:
            clink_ptr_in.next = zext(valid_ivalidBytes,  clink_ptr_width)
        elif ivalidBytes > 0:
            clink_ptr_in.next = valid_pbuff_waddr
        else:
            clink_ptr_in.next = 0

    @always_comb
    def setcwe():
        if (valid_ivalidBytes > 0 and pbuff_we==1) or valid_pbuff_last==1:
            clink_we.next = 1
        else:
            clink_we.next = 0

    clink_waddr  = current_chunk

    clink = memory(
        clink_in, 
        clink_out, 
        clink_raddr, 
        clink_waddr, 
        clink_re,
        clink_we,
        clk, rstn,
        write_through = 1,
        depth=depth, name="link_mem") 


    ################################
    # Store the incoming packets
    
    # Store the incoming packet chunks
    @always(clk.posedge, rstn.negedge)
    def store():
        if rstn==0:
            current_head.next  = 0
            current_chunk.next = 0
            pfifo_in.next = 0
            pfifo_push.next = 0
        else:
            pfifo_push.next = 0
            if ifirst==1:
                current_head.next = free_out 
                if ilast:
                    pfifo_in.next      = free_out
            elif ilast==1:
                pfifo_in.next   = current_head
            if ilast==1:
                pfifo_push.next = 1
            if ivalidBytes > 0:
                if free_avail==0:
                    print("ERROR! Packet buffer is full, please implement backpressure!")
                    assert 0
                else:
                    current_chunk.next = free_out

    pfifo_pop_d1   = Signal(intbv(0)[1:0])
    pfifo_pop_d_ff = flop(pfifo_pop, pfifo_pop_d1, clk, rstn)
    ilast_d        = [ Signal(intbv(0)[1:0])              for _ in range(3)]
    ilast_d_ff     = pipeline(ilast, ilast_d, clk, rstn)
    ifirst_d        = [ Signal(intbv(0)[1:0])              for _ in range(3)]
    ifirst_d_ff     = pipeline(ifirst, ifirst_d, clk, rstn)
    ivalidBytes_d  = [ Signal(intbv(0)[len(ivalidBytes):]) for _ in range(3)]
    ivalidBytes_d_ff = pipeline(ivalidBytes, ivalidBytes_d, clk, rstn)
                    

#    # Link the chunks
#    @always(clk.posedge, rstn.negedge)
#    def link():
#        if rstn==0:
#            clink_we.next    = 0
##            clink_eop_in.next  = 0
#        else:
#            clink_we.next    = 0
##            clink_eop_in.next  = 0
#            if ivalidBytes_d[1] > 0 and ifirst_d[1]==0:
#                clink_we.next     = 1
#            if ilast_d[1]==1:
#                # For the last chunk the next pointer holds the number of valid bytes
#                clink_we.next    = 1
##                clink_eop_in.next  = 1
#                
    oongoing       = Signal(intbv(0)[1:0])                  
    oongoing_d     = [Signal(intbv(0)[1:0]) for _ in range(3)]                  
    oongoing_d_p   = pipeline(oongoing, oongoing_d, clk, rstn)
    odone          = Signal(intbv(0)[1:0])                  
    ocurrent_chunk = Signal(intbv(0)[ clink_addr_width: ])   

    ######################
    # Output the packets


#    pfifo_pop = ongoing==0 and pfifo_empty==0
    # pop the pfifo
    @always_comb
    def popp():
        if (oongoing==0 or olast==1) and pfifo_empty==0:
            pfifo_pop.next = 1
        else:
            pfifo_pop.next = 0

    # Follow the links
    @always_comb
    def eop():
        if clink_re_d[1]==1:
            clink_eop_valid.next = clink_eop_out
        else:
            clink_eop_valid.next = 0
            
    @always_comb
    def clincre():
        if (pfifo_pop==1 or (oongoing==1 and clink_eop_valid==0)):
            clink_re.next = 1
        else:
            clink_re.next = 0


    @always_comb
    def clincra():
        clink_raddr.next = 0
        if pfifo_pop==1:
            clink_raddr.next = pfifo_out
        elif oongoing==1 and clink_eop_valid==0:
            clink_raddr.next = clink_ptr_out[clink_addr_width:]

    # Read the packet chunk
    @always_comb
    def readChunk():
        if pfifo_pop==1:
            pbuff_re.next    = 1
            pbuff_raddr.next = pfifo_out
        elif oongoing==1 and clink_eop_valid==0:
            pbuff_re.next    = 1
            pbuff_raddr.next = clink_ptr_out[ pbuff_addr_width: ]            
        else:
            pbuff_re.next    = 0
            pbuff_raddr.next = 0

   
    @always(clk.posedge, rstn.negedge)
    def retrieve():
        if rstn==0:
            oongoing.next  = 0
        else:
            # Start a new packet
            if pfifo_pop==1:
                oongoing.next = 1 
            # Continue an ongoing packet 
            elif oongoing==1 and clink_eop_valid==1:
                oongoing.next = 0
                    
    @always_comb 
    def setodata():
        odata.next  = pbuff_out
    @always_comb 
    def setofirst():
        ofirst.next = pfifo_pop_d1
    @always_comb 
    def setolast():
        olast.next  = clink_eop_valid
    ovb_width = len(ovalidBytes)
    ovb_max   = ovalidBytes.max
    @always_comb 
    def setovb():
#        if clink_eop_valid==1: # TODO: This should work, but myhdls overzealous range checking asserts. Should be fixed in myhdl-0.8 
        if clink_re_d[1]==1:
            if clink_eop_out==1:
                if clink_ptr_out < ovb_max:  #Just to get rid of the myhdl range error
                    ovalidBytes.next = clink_ptr_out[ovb_width:]
                else:
                    ovalidBytes.next = 0
            else:
                ovalidBytes.next = bytes_per_chunk
        else:
            ovalidBytes.next = 0
            

    ifreein = flop(pbuff_raddr, free_in,   clk, rstn)
    ifreepu = flop(pbuff_re,    free_push, clk, rstn)


    return instances()

