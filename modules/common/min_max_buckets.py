from myhdl import *
from .Common import copySignal, select_rr, flop_e, pass_through
from .calculations import bitlength

"""
File status:
Begun.

"""

def min_max_buckets(available, allowed, queue, valid_bytes, min_bw, max_bw, max_burst, clk, rstn, core_freq, max_pkt, name=""):
    """
    Two bw buckets per queue one min, and one max. 
    If any queue is available and below the min threshold, only those that are below min are allowed.
    If no queue is available and below min, any that is below max is available.

    bandwidths are in bits per 1/core_freq, with the number of fraction
    bits necessary for a granularity of 1kbit/s
    The max deficit is two times the maximum packet.

    TODO: The counters are sized for updating every clock cycle, which is wasteful
    TODO: Counters in memory
    """

    assert len(min_bw)==len(max_bw)==len(available)==len(allowed)
    
    clocks_per_kbit = core_freq
    bits_per_kbit = len(bin(clocks_per_kbit))-2
    frac_bits =  bits_per_kbit

    max_deficit = max_pkt*2
    max_value = max_deficit + max_burst[0].max
    max_bits = frac_bits + len(bin(max_value))-2

    print(name, "Setting up min/max_buckets with params:")
    print("  max_deficit:", max_deficit)
    print("  max_bits:   ", max_bits) 
    print("  buckets:    ", len(min_bw)) 

    def bucket(available, below, drip, update, max_burst, clk, rstn, name=""):
        value = Signal(intbv(0)[max_bits:0])
        @always(clk.posedge, rstn.negedge)
        def bucket_value():
            if rstn==0:
                value.next = max_deficit<<frac_bits
            else:
                next_val = intbv(0)
                next_val[:] = value - update + drip
                if next_val<0:
                    value.next = 0 
                elif next_val>=value.max:
                    value.next = value.max-1
                else:
                    value.next = next_val
                below.next = available and (value <= (max_deficit<<frac_bits)) 
        return instances()
    
    sent_bytes = [Signal(intbv(0)[len(valid_bytes)+frac_bits:]) for _ in min_bw]

    @always_comb
    def calc_bytes():
        for i in range(len(sent_bytes)):
            if queue==i:
                sent_bytes[i].next = vaild_bytes<<frac_bits
            else:
                sent_bytes[i].next = 0
                
    below_min = copySignal(available)
    below_max = copySignal(available)
    min_cnt = []
    max_cnt = []
    for i in range(len(min_bw)):
        min_cnt.append( bucket(
            below       = below_min[i], 
            drip        = min_bw[i], 
            update      = sent_bytes[i], 
            max_deficit = max_deficit[i], 
            clk=clk, rstn=rstn, name=name+".min_cnt%d"%i
            ))
        max_cnt.append( bucket(
            below       = below_min[i], 
            drip        = max_bw[i], 
            update      = sent_bytes[i], 
            max_deficit = max_deficit[i],
            clk=clk, rstn=rstn, name=name+".max_cnt%d"%i
            ))
    
    @always_comb
    def calc_avail():
        if below_min==0:
            allowed.next = available and below_max
        else:
            allowed.next = available and below_min
            
    return instances()
