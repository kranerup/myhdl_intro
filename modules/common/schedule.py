def schedule(group_bw, group_port_list, core_freq=100, min_pkt=64, ifg=20, min_distance=2):
    #print "schedule group_bw", group_bw, "group_ports", group_port_list, "core_freq", core_freq

    rev = False
    port_list = [ x for _, x in sorted(zip(group_bw, group_port_list), reverse=rev)]
    bw = sorted(group_bw, reverse=rev)
    
    #print "sorted bw", bw
    #print "sorted ports", port_list

    quanta = (min_pkt+ifg)*8
    #print "quanta = %s" % quanta 
    groups = len(bw)

    tot_ports = sum([ len(x) for x in port_list])

    tot_bw = 0
    gbw = [0 for _ in range(groups)]
    pbw = []
    for i in range(groups):
        for p in port_list[i]:
            pbw.append(bw[i])
            gbw[i] += bw[i]
            tot_bw += bw[i]
    #print "gbw    = %s" % gbw
    #print "tot_bw = %s" % tot_bw

    utilization = (tot_bw*1.0/quanta)/core_freq
    #print "utilization = (%s/%s)/%s = %s%%" % (tot_bw, quanta, core_freq, utilization*100)
    ord = []
    
    import math
    gcd = tot_bw
    for i in pbw:
        gcd = math.gcd(gcd, i)
    #print "gcd", gcd
    total = tot_bw // gcd
    bandwidth = [x//gcd for x in bw]
    #print "bandwidth", bandwidth

    from copy import copy
    bw_cnt = copy(bandwidth)
    group_cnt = [0 for _ in range(groups)]

    # The principle is this:
    # We start from the lowest speed ports, because they
    # have the laxest timing requirements.
    # We mix toghether the lowest speed ports with the
    # second lowest according to their total bandwidth ratios.
    # Then we iteratively mix in faster and faster ports
    sched = [] # List of group numbers
    def mix(high_list, high_bw, low_list, low_bw):
        # Find the gcd of the total bandwidths
        gcd = math.gcd(high_bw, low_bw)
        #print "high_bw %s, low_bw %s, gcd %s" % (high_bw, low_bw, gcd)
        high = high_bw // gcd
        low  = low_bw // gcd
        #print "high %s, low %s" % (high, low) 
        dup = 1.0*len(high_list) / high
        if dup>1:
            high *= int(dup)
            low  *= int(dup)
        dup = 1.0*len(low_list) / low
        if dup>1:
            high *= int(dup)
            low  *= int(dup)
        hc = 0
        lc = 0
        step = high*1.0 / low
        sc = step/2.0
        sched = []
        for x in range(int(high+low)):
            if sc >= hc+0.5:
                sched.append(high_list[hc%len(high_list)])
                #print "high", sc
                hc+=1
            else:
                sched.append(low_list[lc%len(low_list)])
                #print "low", sc
                lc+=1
                sc+=step
        assert hc==high, "hc %s != high %s " % (hc, high)
        assert lc==low, "lc %s != low %s " % (lc, low)
        return sched
        
    bw_sum = gbw[0]
    sched = []
    sched.extend(port_list[0])
    for i in range(groups-1):
        sched = mix(sched, bw_sum, port_list[i+1], gbw[i+1])
        bw_sum += gbw[i+1]
    #print "length", len(sched)
    #print sched

    dup = []
    for i in range(groups):
        nr = 0
        for p in port_list[i]:
            nr += sched.count(p) 
        dup.append(1.0*nr / (len(port_list[i])*bw[i]))
    assert dup==[dup[0] for _ in range(len(dup))]
    return sched

def min_max_distance(group_port_list, sched):
    #print "Min/Max distances:"
    #print "group_port_list", group_port_list
    #print "sched", sched
    ports = []
    minmax = {}
    for pl in group_port_list:
        ports.extend(pl)
    for p in ports:
        mi = len(sched)
        ma = 0
        cnt=0
        hit = 0
        for i in 2*list(range(len(sched))):
            if hit==1:
                cnt+=1
            if sched[i%len(sched)]==p:
                ma = max(ma, cnt)
                if hit==1:
                    mi = min(mi, cnt)
                hit=1
                cnt=0
            minmax[p] = [mi, ma]
            #print "port %s [%s,%s]" % (p,mi,ma)
    return minmax

if __name__ == "__main__":
    import sys
    import ast

    if len(sys.argv)!=3:
        print("Syntax: python schedule.py list_of_bw list_of_nr_of_ports")
        print("  Where list_of_bw is a list of port bandwidths,")
        print("  and list_of_nr_of_ports is a list of the number")
        print("  ports with each bandwidth. The ports will be")
        print("  numbered in order.")
        exit(1)
    nr = ast.literal_eval(sys.argv[2])
    ports = []
    cnt = 0
    for i in range(len(nr)):
        ports.append([])
        for x in range(nr[i]):
            ports[i].append(cnt)
            cnt+=1

    sched = schedule(
        ast.literal_eval(sys.argv[1]),
        ports
        )
    print("Schedule:")
    print(sched)
    print()
    print("Distance [min,max]")
    dist = min_max_distance(
        ports,
        sched
    )
    for k in dist:
        print("port %s %s" % (k, dist[k]))
