from myhdl import *
from modules.common.Common import hwdir, copySignal
import sys
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
def print_packet(
        first, last, valid_bytes, data, clk, rstn, id=None, express=None, dest_port=None, dest_mask=None,
        nr_of_concurrent=1,
        name=""):

    source = id
    if nr_of_concurrent == 1:
        source = 0
    else:
        source = Signal(modbv(0)[(nr_of_concurrent).bit_length():]) 
        if express!=None:
            @always_comb
            def setsource():
                source.next = concat(id, express)
        else:
            @always_comb
            def setsource():
                source.next = id
        

    print_chunks = 1
    chunk = 8 # hwconf.cell_size//8
    maxpkt = max(hwconf.long_packet_limit, 9600)
    maxchunks = maxpkt//chunk
    hash_w = 32
    
    current_data = [ Signal(modbv(0)[maxpkt*8:]) for _ in range(nr_of_concurrent) ]
    current_hash = [ Signal(modbv(0)[maxpkt*8:]) for _ in range(nr_of_concurrent) ]
    current_len  = [ Signal(modbv(0)[(maxpkt).bit_length():]) for _ in range(nr_of_concurrent) ]
    last_ff  = Signal(modbv(0)[1:])
    source_ff  = Signal(modbv(0)[(nr_of_concurrent).bit_length():])
    data_w = len(data)
    if dest_port!=None:
        dest_port_ff = copySignal(dest_port)
        dest_port_e = 1 
    else:
        dest_port_ff = 0
        dest_port_e = 0 
    if dest_mask!=None:
        dest_mask_ff = [ copySignal(dest_mask) for _ in range(nr_of_concurrent) ]
        dest_mask_e = 1 
    else:
        dest_mask_ff = 0
        dest_mask_e = 0 
  
    # datatmp is separated into an always block to avoid the issue when MyHDL
    # initializes a local modbv. Since the signal width is huge the
    # initialization is not supported by standard complying simulators
    # (verilator).
    datatmp = Signal(modbv(0)[maxpkt*8:])

    @always_comb
    def wide_data():
        "synthesis translate_off"
        datatmp.next = data & ((1<<(valid_bytes*8))-1)
        "synthesis translate_on"

    @checker(clk.posedge, rstn.negedge)
    def printpacket():
        if rstn==0:
            for i in range(nr_of_concurrent):
                current_data[i].next = 0
                current_len[i].next = 0
                if dest_mask_e==1:
                    dest_mask_ff[i].next = 0
            last_ff.next = 0 
            source_ff.next = 0
            if dest_port_e==1:
                dest_port_ff.next = 0
        else:
            printtmp = modbv(0)[chunk*8:]
            source_ff.next = source
            last_ff.next = last
            if dest_port_e==1:
                dest_port_ff.next = dest_port
            if first==1:
                current_data[source].next = datatmp
                current_len[source].next = valid_bytes
                if dest_mask_e==1:
                    dest_mask_ff[source].next = dest_mask
            elif valid_bytes>0:
                current_data[source].next = current_data[source] | (datatmp << (current_len[source]*8))
                current_len[source].next = current_len[source] + valid_bytes

            if last_ff==1:
                print("%s: PACKET " % (name), end=' ')
                if print_chunks==1:
                    cnt = (current_len[source_ff] + (chunk - 1)) // chunk
                    while cnt > 0:
                        cnt -= 1
                        printtmp[:] = (current_data[source_ff] >> (cnt*chunk*8))
                        # chunk*2 is because the width is in hex chars:
                        print(" %d-%dDATA(%d)" % (cnt, chunk*2, printtmp), end=' ')
                else:
                    print("DATA(%d)" % current_data[source_ff], end=' ')
                print(", len:%s" % current_len[source_ff], end=' ')
                if dest_port_e==1:
                    print(", dest_port:%s" % dest_port_ff, end=' ')
                if dest_mask_e==1:
                    print(", dest_mask:%s" % dest_mask_ff[source_ff], end=' ')
                if nr_of_concurrent>1:
                    print(", id:%s" % source_ff, end=' ')
                print("")
        
    return instances()
            
