from myhdl import *
from .Common import copySignal, select_rr, flop, flop_e, pass_through
from unittesting.Debug import DebugDb
import math

"""
File status:
The bw_scheduler is a quick hack and completely untested. It seems to work though.

There is a skeleton for a testbench, but it doesn't test anything.
"""

def bw_scheduler(in_available, selected, valid, clk, rstn, bw, tot_bw=None, work_conserving=1, cycles_between_visits=3, name=""):
    """
    Schedules those maked as available in accordance with their stated bandwidth in relation to the total bandwidth.

    TODO: Support best effort
    """
    print("Instanciated bw_scheduler %s with bw %s" % (name, bw))

    # If there are different port speeds 
    if bw != [bw[0] for _ in range(len(bw))]:
        assert False, "Dont use the bw_scheduler. Use the mixed_scheduler"
                
    if not work_conserving:
        if tot_bw!=None:
            print("Warning!", name, "tot_bw is ignored when work_conserving is set to 0")
        last = bw[0]
        for i in bw:
            if last != i:
                print("ERROR!", name, "Non work-conserving is only supported when all ports have the same bandwidth")
                assert False

    if tot_bw == None:
        tot_bw = sum(bw)
    assert sum(bw) <= tot_bw

    nr_served = len(bw)
    print(name, "nr_served", nr_served)
    print(name, "bw", bw)
    print(name, "cycles_between_visits", cycles_between_visits) 


    # Make sure available is a signal
    available_flat = Signal(intbv(0)[len(in_available):0])
    available = Signal(intbv(0)[len(in_available):0])
    iflat = pass_through(in_available, available_flat, name=name+".ina") 

    gcd = tot_bw
    for i in bw:
        gcd = math.gcd(gcd, i)
#    print "gcd", gcd
    total     = tot_bw // gcd
    bandwidth = [ x/gcd for x in bw ]
 
    bw_cnt = [ Signal(intbv(0, min=0, max=2*total+1)) for _ in range(nr_served) ]
    eligable   = copySignal(available)
    nervous    = copySignal(available)
    filtered   = copySignal(available)

    last     = copySignal(selected)
    sel_cool = copySignal(selected)
    valid_cool  = Signal(intbv(0)[1:0])
    sel_rest   = copySignal(selected)
    valid_rest = Signal(intbv(0)[1:0])
    isel1  = select_rr(filtered,  last, sel_cool, valid_cool, name+".bwsel1")
    isel2  = select_rr(available, last, sel_rest, valid_rest, name+".bwsel2")
    
    visit_cnt = [ Signal(modbv(0)[cycles_between_visits.bit_length():]) for _ in range(nr_served) ]
    visit_filter = Signal(modbv(0)[nr_served:])
    
    if work_conserving:
        print(name, "work-conserving scheduler instanciated")
        selected_x  = copySignal(selected) 
        valid_x  = copySignal(valid) 

        zLast = flop_e(selected_x, last, valid_x, clk, rstn)
        if cycles_between_visits == 0:
            visit_filter = (1 << nr_served) - 1
        elif cycles_between_visits == 1:
            @always(clk.posedge, rstn.negedge)
            def vfilt():
                if rstn==0:
                    visit_filter.next = (1 << nr_served) - 1  
                else:
                    if valid_x==1:
                        visit_filter.next[selected_x] = 0
                    for i in range(nr_served):
                        if visit_filter[selected_x] == 0:
                            visit_filter.next[selected_x] = 1
        else:
            @always(clk.posedge, rstn.negedge)
            def vcnt():
                if rstn==0:
                    for i in range(nr_served):
                        visit_cnt[i].next = cycles_between_visits
                    visit_filter.next = (1 << nr_served) - 1  
                else:
                    for i in range(nr_served):
                        if visit_cnt[i] < cycles_between_visits:
                            visit_cnt[i].next = visit_cnt[i] + 1
                        if visit_cnt[i] == cycles_between_visits-1:
                            visit_filter.next[i] = 1
                    if valid_x==1:
                        visit_cnt[selected_x].next = 0
                        visit_filter.next[selected_x] = 0

        @always_comb
        def filt_visit():
            available.next = available_flat & visit_filter
                        
        @always_comb
        def above():
            temp = intbv(0)[nr_served:]
            for i in range(nr_served):
                if bw_cnt[i] <= total:
                    temp[i] = 1
            eligable.next = temp

        @always_comb
        def filter():
            filtered.next = available & eligable

        @always_comb
        def arb():
            if valid_cool==1:
                selected_x.next = sel_cool
                valid_x.next    = 1
            elif valid_rest==1:
                selected_x.next = sel_rest
                valid_x.next    = 1
            else:
                selected_x.next = 0
                valid_x.next    = 0

        zFsel = flop(selected_x, selected, clk, rstn)
        zFval = flop(valid_x, valid, clk, rstn)

        select_onehot = [ Signal(intbv(0)[1:0]) for _ in range(nr_served) ]
        @always_comb
        def onehot():
            temp = intbv(0)[nr_served:]
            for i in range(nr_served):
                if valid_x==1 and selected_x==i:
                    temp[i] = 1
            for i in range(nr_served):
                select_onehot[i].next = temp[i]

        def counter(available, sel, bw_cnt, bandwidth, total, clk, rstn, nr=0):
            @always(clk.posedge, rstn.negedge)
            def count():
                if rstn==0:
                    bw_cnt.next = 2*total-bandwidth
                else:
                    if bw_cnt - bandwidth >= 0:
                        bw_cnt.next = bw_cnt - bandwidth
                    elif available==0:
                        bw_cnt.next = total - bandwidth
                    elif sel==0:
                        "synthesis translate_off"
                        print("ERROR! BW scheduler",  nr, "underflow!")
                        assert False
                        "synthesis translate_on"
                        bw_cnt.next = 0
                    if int(sel)==1:
                        #print nr, "selected_x"
                        if bw_cnt + total - bandwidth <= total * 2:
                            #print "  ", bw_cnt, total, bandwidth
                            bw_cnt.next = bw_cnt + total - bandwidth
                        else:
                            #print "Warning! Overflow", nr
                            bw_cnt.next = total*2
            return instances()

        icnt = []
        for i in range(nr_served):
            icnt.append(counter(available[i], select_onehot[i], bw_cnt[i], bandwidth[i], total, clk, rstn, i))
    else:
        print(name, "non-work-conserving scheduler instanciated")
        available = available_flat
        cnt = Signal(intbv(0, min=0, max=nr_served))
        @always(clk.posedge, rstn.negedge)
        def round_robin():
            if rstn==0:
                cnt.next      = 0
                selected.next = 0
                valid.next    = 0
                last.next     = 0
            else:
                if cnt==nr_served-1:
                    cnt.next = 0
                else:
                    cnt.next = cnt + 1
                if available[cnt]==1:
                    selected.next = cnt
                    valid.next    = 1
                    last.next = cnt
                else:
                    selected.next = 0
                    valid.next    = 0

    return instances()
