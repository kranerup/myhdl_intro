from myhdl import *
from .Common import copySignal

"""
File status:
The fixed_scheduler is a simple fixed scheduler for mixed port speeds.
It does not try to leave bubbles to match the exact bandwidth, but only
schedules the ports weighted to their bandwidths. The halts will create 
the bubbles.
"""

def fixed_scheduler(port, clk, rstn, sched, port_offset=0, repeat=0, port_start=None, name=""):
    print("Instanciated fixed_scheduler %s with schedule %s" % (name, sched))
    from modules.common.schedule import schedule, min_max_distance
    pattern_length = len(sched)

    lp = len(port)
    cnt = Signal(intbv(0, min=0, max=pattern_length))

    if repeat == 0:
        @always(clk.posedge, rstn.negedge)
        def machine():
            if rstn==0:
                port.next = port_offset
                cnt.next = 0
            else:
                p = modbv(0)[lp:]
                if cnt==pattern_length-1:
                    cnt.next = 0
                else:
                    cnt.next = cnt + 1
                p[:] = sched[cnt]
                port.next = p + port_offset
    else:
        repeat_cnt = Signal(intbv(0, min=0, max=repeat+1))
        @always(clk.posedge, rstn.negedge)
        def machine():
            if rstn==0:
                port.next = port_offset
                port_start.next = 0
                cnt.next = 0
                repeat_cnt.next = 0
            else:
                p = modbv(0)[lp:]
                if repeat_cnt == repeat:
                    repeat_cnt.next = 0
                    port_start.next = 0
                    if cnt==pattern_length-1:
                        cnt.next = 0
                    else:
                        cnt.next = cnt + 1
                else:
                    repeat_cnt.next = repeat_cnt +1
                    if repeat_cnt == 0:
                        port_start.next = 1
                    else:
                        port_start.next = 0
                p[:] = sched[cnt]
                port.next = p + port_offset
        
    
    return instances()

def fixed_scheduler_avail(in_available, selected, valid, clk, rstn, sched, port_offset=0, name=""):
    print("Instanciated fixed_scheduler_avail %s with schedule %s" % (name, sched))

    mp = (1<<len(in_available))-1
    port = Signal(intbv(0, min=-1, max=mp))
    iFsch = fixed_scheduler(port, clk, rstn, sched, name=name+".iFsch")

    @always_comb
    def comb():
        if port != -1:
            selected.next = port
            valid.next = in_available[port]
        else:
            selected.next = 0
            valid.next = 0
            
    return instances()
