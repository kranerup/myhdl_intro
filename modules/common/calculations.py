#!/usr/bin/python3
"""
File status: The calculations module was supposed to contain all
methods for calculating hw parameters based on top level
parameters. 

Almost all of that is now spread across the code base or in
Common.py 

To get a better overview it would be a good idea to clean this up and
have all the calculations in one place. Here that is.
"""
import sys
from math import ceil 
import numbers
from math import gcd
from functools import reduce

# _round = round
#
# def python2round(f):
#     """Rounding on Python3 is different.
#     This implements Python 2 rounding in Python 3
#     """
#     if _round(f + 1) - _round(f) != 1:
#         return f + abs(f) / f * 0.5
#     return _round(f)
#
# round = python2round
#

decimals = 9
def macBusFreq(bw, width, minPkt=480, ifg=192, maxPkt=32768*8, quiet=0):
    throughput_freq = 1.0*bw/width
    packet_freq = 1.0*bw/(minPkt+ifg)
    freq_max = max(throughput_freq, packet_freq)
    for i in range(1, maxPkt//width):
        cell_freq = (i+1.0)*bw/(width*i+8+ifg)
        freq_max = max(freq_max, cell_freq)
            #print "     ->  freq %s" % (freq)
    return round(freq_max, decimals)

def pktCycle(bw, fc, minPkt=512, ifg=0):
    bw = float(bw)
    fc = float(fc)

    packet_rate = bw/(minPkt+ifg)
    packet_cycles = fc/packet_rate
    return packet_cycles

def bitlength(n,start=0):
    '''
    Calculate the bit length of a constant number
    '''
    num = n+start
    if num == 0:
        return 0

    else:
        
        i = 0
        s = 1
        while True:
            i +=1
            s = s * 2
            if s >= num:
                break
        return i

from random import random, randint
from random import triangular
from math import floor

def packet_length(minPktLen=None, maxPktLen=None, tcconf={}):
    if minPktLen is None:
        minPktLen = tcconf['min_pkt']
    if maxPktLen is None:
        maxPktLen = tcconf['max_pkt']
    assert tcconf['shortErrorProbability'] + tcconf['longErrorProbability'] <= 1
    lengthseed = random()
    if lengthseed < tcconf['shortErrorProbability']:
        r = int(floor(triangular( tcconf['minShortError'], minPktLen, tcconf['minShortError'])))
        print("creating short packet. len", r, "length prob:", tcconf['shortErrorProbability'], "lseed:", lengthseed) 
    elif lengthseed < (tcconf['shortErrorProbability'] + tcconf['longErrorProbability']):
        r = int(floor(triangular(maxPktLen,  tcconf['maxLongError'], maxPktLen )))
        print("creating long packet. len", r, "length prob:", tcconf['longErrorProbability'], "lseed:", lengthseed) 
    else:
        r = int(floor(triangular(minPktLen, maxPktLen, minPktLen)))
        # print("calculations.packet_length:", minPktLen, maxPktLen, r)
    return r
        
def safe_filename(string):
    import pprint
    # filename = pprint.pformat(string)
    filename = string
    if filename==None:
        filename = ""
    keepcharacters = (' ', '.', '_')
    "".join(c for c in filename if c.isalnum() or c in keepcharacters).rstrip()
    return filename 

def get_ingress_ifg_list(hwconf, tb_ingress_ifg_bits):
    if isinstance(hwconf, dict):
        ifg = hwconf['ifg']
        nr_of_ports = hwconf['nr_of_ports']
        nr_of_internal_ports = hwconf['nr_of_internal_ports']
    else:
        ifg = hwconf.ifg
        nr_of_ports = hwconf.nr_of_ports
        nr_of_internal_ports = hwconf.nr_of_internal_ports        
    
    if tb_ingress_ifg_bits in ["default", None]:
        return ifg
    elif isinstance(tb_ingress_ifg_bits, int):
        return [tb_ingress_ifg_bits for _ in range(nr_of_ports + nr_of_internal_ports)]
    elif isinstance(tb_ingress_ifg_bits, list):
        return tb_ingress_ifg_bits
    else:
        assert False, "ERROR! Unknown format %¤s of tb_ingress_ifg_bits %s" % (type(tb_ingress_ifg_bits).__name__, tb_ingress_ifg_bits)
        
def get_avg_ifg(hwconf, ports):
    sum_ifg = 0
    sum_bw = 0.0
    for i in ports:
        sum_bw += hwconf.port_bw[i]
        sum_ifg += hwconf.port_bw[i]*hwconf.ifg[i]
    return sum_ifg / sum_bw

def max_pkt_cycles(hwconf, maxLen=None,ifgIn=None,maxBytes=None,nr_of_packets=1,margin=0, port=None):
    print("max_pkt_cycles maxLen=%s, ifg=%s, maxBytes=%s" % (maxLen,ifgIn,maxBytes) )
    if isinstance(ifgIn, int):
        ifg = ifgIn
    elif port==None:
        ifg = max(get_ingress_ifg_list(hwconf, ifgIn))
    else:
        ifg = (get_ingress_ifg_list(hwconf, ifgIn))[port]
    if maxBytes==None:
        if port==None:
            mBytes = min(hwconf.port_width)//8
        else:
            mBytes = hwconf.port_width[port]//8
    elif isinstance(maxBytes, list):
        mBytes = min(maxBytes)
    else:
        mBytes = maxBytes
    one_pkt_cycles = (maxLen-1+ifg//8-1)//mBytes+1
    cycles = one_pkt_cycles*nr_of_packets+margin
    return cycles

def cell_headroom(hwconf, i2e=0, freq=None):
    # For each slice find the cell headroom in bits 
    lverbose = False
    stripped_fcs = 0 # FCS is included in IFG
    if freq==None:
        core_freq = hwconf.core_freq
    else:
        core_freq = freq
    required_cell = 0
    for ss in range(hwconf.nr_of_pb):
        avg_ifg = get_avg_ifg(hwconf, hwconf.slice_ports[ss])
        bw = hwconf.slice_bw[ss]
        minPkt = min_pkt_bits(hwconf)
        if lverbose: print("cell_headroom", bw, core_freq, avg_ifg+stripped_fcs,
                           minPkt,
                           hwconf.long_packet_limit*8)
        try:
            width = macBusWidth(bw, core_freq, ifg=avg_ifg+stripped_fcs,
                                        minPkt=minPkt,
                                        maxPkt=hwconf.long_packet_limit*8 )
        except:
            return -1
        required_cell = max(required_cell, width)

    if lverbose: print("cell_headroom returns", hwconf.cell_size, required_cell, i2e, hwconf.cell_size - required_cell - i2e)
    return hwconf.cell_size - required_cell - i2e 

def min_pkt_bits(hwconf):
    minPkt = hwconf.short_packet_limit*8
    if hwconf.wirespeed_packet_limit:
        minPkt = max(minPkt, hwconf.wirespeed_packet_limit*8)
    return minPkt

def frequency_headroom(hwconf, i2e=0):
    # For each slice find the frequency headroom, taking i2e header into account
    #print "Call cell_headroom"
    sys.stdout.flush()
    bits = cell_headroom(hwconf, i2e)
    freq = hwconf.core_freq+1
    minhr = 1000000
    for ss in range(hwconf.nr_of_pb):
        bw = hwconf.slice_bw[ss]
        minPkt = min_pkt_bits(hwconf)
        avg_ifg = get_avg_ifg(hwconf, hwconf.slice_ports[ss])
        print("frequency_headroom: slice %s average IFG %s" % (ss, avg_ifg))
        packet_freq = 1.0*bw/(minPkt+avg_ifg)
        if bits < 0:
            hr = -1
            while cell_headroom(hwconf, i2e, freq-hr) < 0:
                hr -= 1
            minhr = min(minhr, hr)
        else:
            hr = 1
            while cell_headroom(hwconf, i2e, freq-hr) >= 0:
                if freq-hr-1 < packet_freq:
                    break
                hr += 1
            minhr = min(minhr, hr-1)
    return minhr

# Calculate the widths and numbers of wrr schedulers needed to
# support any single level configuration for a certain number of queues.
def hrr_full_set(queues, max_width="default", mult=1): # max_width is the maximum with of any single scheduler
    if max_width=="default":
        mw = queues
    else:
        mw = max_width
    assert queues>1
    r = []
    p2 = mw
    while p2 > 1:
        div = queues//p2
        wider = 0
        for s in r:
            wider += s['nr']
        #print("%s // %s == %s. higher = %s -> nr %s" % (queues, p2, div, wider, div-wider))
        if div-wider>0:
            r += [ {'width':p2, 'nr':div-wider} ]
        p2 -= 1
    if mult>1:
        for i in range(len(r)):
            r[i]['nr'] = int( ceil( r[i]['nr'] * mult ) )
    return r
def hrr_sum_sets(sets):
    r = []
    for S in sets:
        for s in S:
            #print("s", s)
            found = 0
            for t in r: 
                #print("  t", t)
                if s['width'] == t['width']:
                    t['nr']+=s['nr']
                    found = 1
                    break
            if not found:
                r.append(s)
    return r
def hrr_nr_of_wrr(sets):
    nr = 0
    for s in sets:
        for w in s:
            nr += s['nr']
    return nr

def hrr_scale_config(queue_config, factor):
    from copy import deepcopy
    # Scale the values by factor; factor can be int or list (per port)
    if isinstance(factor, list):
        f = factor
    else:
        f = [factor for _ in range(len(queue_config['port_queues']))] 
    new_config = {}
    set_factor = {}
    new_config['port_queues'] = []
    for p in range(len(queue_config['port_queues'])):
        v = queue_config['port_queues'][p]
        if isinstance(v, int):
            new_config['port_queues'].append(int(ceil(v*f[p])))
        elif isinstance(v, str):
            set_factor[v] = f[p]
            new_config['port_queues'].append(v)
        else:
            assert False
    if 'set' in queue_config:
        new_config['set'] = {}
        for s in queue_config['set']:
            new_config['set'][s] = deepcopy(queue_config['set'][s])
            for v in queue_config['set'][s]:
                assert s in set_factor, "ERROR! config %s contains unused set %s"
                new_config['set'][s][v] = int(ceil(queue_config['set'][s][v]*set_factor[s]))
    return new_config

def hrr_inc_order(hrr_config, queue_config):
    parsed_queues = parse_queue_config( queue_config )
    for ss in range(len(hrr_config)):
        wrr_w = hrr_config[ss]['wrr_w']
        for p,v in enumerate(hrr_config[ss]['order_config']['port_queues']):
            if isinstance(v, int):
                extra = 0
                if v >= wrr_w:
                    # One extra order per WRR scheduler needed
                    extra = int(ceil(v/wrr_w))
                elif v <= parsed_queues["max_list"][p]:
                    # One extra order for the top WRR scheduler
                    extra = 1
                hrr_config[ss]['order_config']['port_queues'][p] = v + extra 


def parse_queue_config(config):
    queue_base_list = []
    default_offset_list = []
    default_queues_list = []
    qv_base = []
    flex_ports = []
    # Queue config
    qcnt = 0
    last_qcnt = 0
    inset = 0
    pcnt = 0
    port_max_queues = []
    port_sum_queues = []
    set_max_queues = 0
    ocnt = 0
    for p, qs in enumerate(config['port_queues']):
        qv_base.append(0 if p == 0 else qv_base[-1] + port_max_queues[-1])
        if isinstance(qs, int):
            inset = 0
            queue_base_list.append(qcnt)
            qcnt+=qs
            last_qcnt = qcnt
            port_max_queues.append(qs)
            port_sum_queues.append(qs)
            default_offset_list.append(0)
            default_queues_list.append(qs)
        elif qs in config['set']:
            flex_ports.append(pcnt)
            queue_base_list.append(last_qcnt)
            port_max_queues.append(config['set'][qs]['max'])
            port_sum_queues.append(config["set"][qs]["sum"])
            set_max_queues = max(config['set'][qs]['sum'], set_max_queues)
            default_offset_list.append(ocnt)
            default_queues_list.append(config['set'][qs]['default'])
            if inset!=qs:
                ocnt = config['set'][qs]['default']
                last_qcnt = qcnt
                qcnt+=config['set'][qs]['sum']
                inset = qs
            else:
                ocnt += config['set'][qs]['default']
        else:
            assert False
        pcnt+=1
    return {
        'base_list':queue_base_list,
        'max_list':port_max_queues,
        'sum_list':port_sum_queues,
        'set_max':set_max_queues,
        'default_offset':default_offset_list,
        'default_queues':default_queues_list,
        'total':qcnt,
        'flex': flex_ports,
        'qv_base': qv_base,
    }


def align_up( val, alignment ):
    assert isinstance( alignment, numbers.Integral )
    ival = int( ceil( val ) )
    return (val + alignment - 1) // alignment * alignment


def cellTiming( nr_cells, T_line_bit, T_bus_cyc, bits_per_cell, T_ifg_bits, min_pkt, packet_increment ):
    """ Check timing of transferring nr_cells over the bus vs. the worst case 
        packet arrival time for this nr_cells.
        Worst case for a cell is a packet that just spills over from previous
        cell. I.e. the shortest packet that requires nr_cells cells.
        For the first cell there is no spill over and the worst case is the
        minimum packet size.
        In case the minimum packet is longer than nr_cells then the cell timing
        is not constrained by this cell count.
    """
    debug = False
    T_cell = T_bus_cyc
    T_pkt_bit = T_line_bit
    T_cells = nr_cells * T_cell
    all_cell_bits = nr_cells * bits_per_cell
    min_pkt_rest = min_pkt % packet_increment
    if debug:
        print("---- nr_cells", nr_cells)
        print("T_cell", T_cell)
        print("T_cells", T_cells)
        print("packet_increment", packet_increment)
        print("tot-cell-bits", all_cell_bits)
    if min_pkt > all_cell_bits:
        # i.e. there is no valid packet length with nr_cells cells
        if debug: print("min-pkt {} is longer than {} cells ({} bytes)".format(min_pkt, nr_cells, all_cell_bits/packet_increment))
        return True
    # shortest packet that will be nr_cells long. It will be nr_cells-1 long
    # plus one byte to spill over into next cell.
    non_spill_cell_bits = (nr_cells-1) * bits_per_cell
    if debug: print('non_spill_cell_bits', non_spill_cell_bits)
    # round up to packet_increment
    # this should not round up, packet length is n * packet_increment + offset,
    # therefore packet_bits must be calculated differently
    #packet_bits = align_up( non_spill_cell_bits + 1, packet_increment )
    spill_over = non_spill_cell_bits + 1
    # spill_over >= n * packet_increment + min_pkt_rest 
    packet_bits = packet_increment * (spill_over // packet_increment) + min_pkt_rest
    if packet_bits <= non_spill_cell_bits: # roundup did not pass cell boundary so add one byte
        packet_bits += packet_increment
    if debug: print('aligned packet bits', packet_bits)
    if packet_bits < min_pkt:
        # Spill over is not possible since that packet length is not valid. The
        # shortest packet arrival/length for this number of cells is therefore
        # min_pkt.
        if debug: print("minimum spill over packet size {} is shorter than min packet {}".format(packet_bits, min_pkt))
        shortest = min_pkt
    else:
        shortest = packet_bits
    T_pkt = shortest * T_pkt_bit + T_ifg_bits
    if debug:
        print("shortest", shortest, shortest/float(packet_increment))
        print("T_pkt", T_pkt)
        print("T diff", T_pkt - T_cells)
    return T_pkt > T_cells or abs(T_pkt - T_cells) < T_pkt * 0.000001  # T_pkt > T_cells


def minBusWidth2( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment=8, packet_increment=8 ):
    """
     bw: Mbit/s
     bus_freq: MHz
     minPkt: bits
     maxPkt: bits
     ifg: bits
     packet_increment: bits
     bus_alignment: bits
    """
    bus_freq_hz = bus_freq * 1e6
    bw_bit = bw * 1e6
    debug = False
    verbose = False
    
    if verbose: print("minBusWidth2", bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment )
    assert (maxPkt - minPkt) % packet_increment == 0, """
      Packet lengths must be aligned of the form: n * {} + {}.
      Min-packet:{} max-packet:{} alignment:{}""".format(
        packet_increment, minPkt % packet_increment, minPkt, maxPkt, packet_increment )

    # Iterate over all possible cell/bus sizes
    for busw in range(bus_alignment, maxPkt+bus_alignment, bus_alignment):
        if debug: print("======= bus_width {} bits".format(busw))
        cell_bits = busw
        T_line_bit = 1.0/bw_bit
        T_bus_cyc = 1.0/bus_freq_hz
        T_ifg_bits = ifg * T_line_bit
        max_pkt_cells = int(ceil( float(maxPkt) / cell_bits ))
        if debug:
            print("cell_bits", cell_bits)
            print("T_ifg_bits", T_ifg_bits)
            print("T_line_bit", T_line_bit)
            print("T_bus_cyc", T_bus_cyc)
            print("max_pkt_cells", max_pkt_cells)
        busw_ok = True
        # for each possible cell count of a packet check the cell timing
        for nr_cells in range(1, max_pkt_cells+1):
            bw_ok = cellTiming(
                nr_cells = nr_cells,
                T_line_bit = T_line_bit,
                T_bus_cyc = T_bus_cyc,
                bits_per_cell = cell_bits,
                T_ifg_bits = T_ifg_bits,
                min_pkt = minPkt,
                packet_increment = packet_increment )
            if debug: print("cellTiming cell-width:{} cells:{} ok:{}".format( busw, nr_cells, bw_ok ))
            if not bw_ok:
                busw_ok = False
                break
        if busw_ok:
            return busw
    assert False, "minBusWidth2 Can not find a possible bus width. %s" % str( [bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment] )
            
    
def minBusWidth( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment=8, packet_increment=8, ):
    """
     bw: Mbit/s
     bus_freq: MHz
     minPkt: bits
     maxPkt: bits
     ifg: bits
     packet_increment: bits
     bus_alignment: bits
    """
    bus_freq_hz = bus_freq * 1e6
    bw_bit = bw * 1e6
    verbose = False
    last_fail = None

    if verbose: print("minBusWidth: ", bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment)
    
    assert (maxPkt - minPkt) % packet_increment == 0, """
      Packet lengths must be aligned of the form: n * {} + {}.
      Min-packet:{} max-packet:{} alignment:{}""".format(
        packet_increment, minPkt % packet_increment, minPkt, maxPkt, packet_increment )

    # Iterate over all possible cell/bus sizes
    for busw in range(bus_alignment, maxPkt+bus_alignment, bus_alignment):
        if verbose: print("==== bus_width", busw)
        # for all possible packet lengths check the packet arrival frequency
        # vs. the bus frequency, taking packet to cell fragmentation into
        # account.
        for pkt_len in range( minPkt, maxPkt+1, packet_increment ):
            if verbose: print('--- pkt_len', pkt_len)
            arrival_distance = float(pkt_len + ifg) / bw_bit
            if verbose: print(arrival_distance)
            avail_bus_cycles_per_packet = arrival_distance / ( 1 / bus_freq_hz )
            if verbose: print(avail_bus_cycles_per_packet)
            bus_cycles = ceil( float(pkt_len) / busw )
            if verbose: print('bus_cycles', bus_cycles, avail_bus_cycles_per_packet)
            if bus_cycles > avail_bus_cycles_per_packet and (
                abs( bus_cycles - avail_bus_cycles_per_packet ) > avail_bus_cycles_per_packet * 0.000001 ):
                if verbose: print("excess cycles")
                last_fail = (pkt_len, busw, arrival_distance, avail_bus_cycles_per_packet, bus_cycles)
                break
        else:
            if verbose: print("success", busw)
            return busw
    
    assert False, "minBusWidth Can not find a possible bus width: %s" % str([bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment])

def all_mbw( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment=8, packet_increment=8 ):
    verbose = False
    with_orig = False

    if with_orig:
        try:
            orig = macBusWidth(bw=int(bw/1e6),
                              freq=bus_freq/1e6,
                              minPkt=minPkt,
                              maxPkt=maxPkt,
                              ifg=ifg )
        except AssertionError:
            orig = 0
            pass
        except ZeroDivisionError:
            orig = 0
            pass

    per_byte = minBusWidth( bw, bus_freq, minPkt*8, maxPkt*8, ifg*8, bus_alignment, packet_increment )
    per_cell = minBusWidth2( bw, bus_freq, minPkt*8, maxPkt*8, ifg*8, bus_alignment, packet_increment )
    all_equal = per_byte == per_cell
    if with_orig:
        all_equal = all_equal and per_cell == orig
    if not all_equal or verbose:
        print("bw:{} bfrq:{} minp:{} maxp:{} ifg:{} align:{}".format( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment ))
        if with_orig:
            print("orig:{:5d} per-byte:{:5d} per-cell:{:5d} equal:{}".format(orig, per_byte, per_cell, all_equal))
        else:
            print("per-byte:{:5d} per-cell:{:5d} equal:{}".format( per_byte, per_cell, all_equal))
    assert per_cell % bus_alignment == 0
    return all_equal

def macBusWidth(bw, freq, ifg=192, minPkt=480, maxPkt=1500*8, quiet=0, bus_alignment=8, packet_increment=8 ):
    """
     bw:     Mbit/s
     req:    MHz
     minPkt: bits
     maxPkt: bits
     ifg:    bits
     packet_increment: bits
       packet lengths from minPkt and upwards always increase by this amount
     bus_alignment: bits
       bus/cell size will be a multiple of this
    """
    return all_mbw2( bw, freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment )

def all_mbw2( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment=8, packet_increment=8 ):
    verbose = False
    per_byte = minBusWidth( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment )
    per_cell = minBusWidth2( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment )
    all_equal = per_byte == per_cell
    if not all_equal or verbose:
        print("macBusWidth bw:{} bfrq:{} minp:{} maxp:{} ifg:{} bus-align:{} pkt-align:{} -> cell-size:{}".format( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment, per_cell ))
        if not all_equal: print("per-byte:{:5d} per-cell:{:5d} equal:{}".format( per_byte, per_cell, all_equal))
    assert per_cell % bus_alignment == 0
    return per_cell

def unittest():
    ## 8-bit
    #w = macBusWidth(bw=1000, freq=125, ifg=(20*8 + 32),
    #                minPkt=480, maxPkt=1500*8 )
    #w = macBusWidth(bw=1000, freq=125, ifg=0,
    #                minPkt=8, maxPkt=9600*8 )
    ## 16-bit
    #w = macBusWidth(bw=1000, freq=125.0/2, ifg=(20*8 + 32),
    #                minPkt=480, maxPkt=1500*8 )
    #w = macBusWidth(bw=1000, freq=125.0/2, ifg=32,
    #                minPkt=(60*8), maxPkt=1500*8 )
    # 143 bytes:
    #w = macBusWidth(bw=1000, freq=1.49, ifg=(20*8+32),
    #                minPkt=(60*8), maxPkt=1500*8 )
    # 60*8 bytes:
    #w = macBusWidth(bw=1000, freq=2.084, ifg=0,
    #                minPkt=(60*8), maxPkt=60*8 )
    #w = macBusWidth(bw=1000, freq=1.49 , ifg=(20*8+32),
    #                minPkt=(60*8), maxPkt=4*60*8 )
    #print w

    print(all_mbw2(25350080.3768, 1675.93735487, 44932, 44938+2, 2514, bus_alignment=1, packet_increment=8))

    print(all_mbw2( 1000, 1.49, 60*8+1, 1500*8+1, 24*8, bus_alignment=1, packet_increment=8 ))
    for bus_alignment in range(1, 8):
        print(all_mbw2( 1000, 1.49, 60*8+1, 1500*8+1, 24*8, bus_alignment=bus_alignment, packet_increment=8 ))

    all_mbw( 1e9, 1.49e6, 60, 1500, 24, 1 )

    all_mbw( 200e9, 156.25e6, 160, 160, 0, 8 )

    all_mbw(800000000.0, 1500000.0, 60, 128, 12, 8)

    all_mbw( 1e9, 1.49e6, 60, 1500, 24, 8 )

    for algn in range(1, 16+1):
        all_mbw( 1e9, 1.49e6, 60, 1500, 24, algn )


    all_mbw( 100e9, 400e6, 60, 1500, 24, 8 )
    all_mbw( 1e9, 1.25e6, 100, 100, 0, 8 )

    # 8-bit
    all_mbw( 1e9, 125e6, 60, 1500, 24, 8 )
    # 16-bit
    all_mbw( 1e9, 125e6//2, 60, 1500, 24, 8 )
    all_mbw( 1e9, 125e6//2, 60, 1500, 4, 8 )
    # 60 bytes:
    all_mbw( 1e9, 2.084e6, 60, 60, 0, 8 )

    all_mbw( 1e9, 1.49e6, 60, 4*60, 24, 8 )

    for i in range(1000000):
        if randint(0, 10) == 0:
            bus_alignment = 1
        elif randint(0, 10) == 0:
            bus_alignment = randint(1, 24)
        else:
            bus_alignment = randint(1, 1000)
        if randint(0, 3) == 0:
            packet_increment = 8
        else:
            packet_increment = randint(1, 32)

        wide_pkt_range = random() > 0.5
        minPkt = randint(1, 10000*8)
        if wide_pkt_range:
            maxPkt = minPkt + packet_increment * randint(0, 10000 )
        else:
            maxPkt = minPkt + packet_increment * randint(0, 10)
        small_ifg = randint(0, 1)
        if small_ifg:
            ifg = randint(0, 10*8)
        else:
            ifg = randint(0, 1000*8)
        bw = random() * 10**(random() * 10 + 4) / 1e6

        bus_freq = bw / ( 10000 * (1+random()) )


        all_mbw2( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment, packet_increment ) 
        

    for i in range(1000000):
        wide_pkt_range = random() > 0.5
        minPkt = int( random() * 10000 + 1 )
        if wide_pkt_range:
            maxPkt = int( random() * 10000 + minPkt )
        else:
            maxPkt = minPkt + randint(0, 10)
        small_ifg = randint(0, 1)
        if small_ifg:
            ifg = randint(0, 10)
        else:
            ifg = int( random() * 1000 )
        bw = random() * 10**(random() * 10 + 4)
        #print "bw",bw
        bus_freq = bw / ( 10000 * (1+random()) )
        #print "bus_freq",bus_freq
        if randint(0, 10) == 0:
            bus_alignment = 1
        elif randint(0, 10) == 0:
            bus_alignment = randint(1, 24)
        else:
            bus_alignment = randint(1, 1000)
        all_mbw( bw, bus_freq, minPkt, maxPkt, ifg, bus_alignment ) 
        
    all_mbw( 1e9, 1.49e6, 60, 4*60, 24, 8 )

    for bw in [ 1e9, 2e9, 0.8e9 ]:
        for bfrq in [ 1.4e6, 1.5e6, 1.6e6 ]:
            for minp in [ 60, 61, 62 ]:
                for maxp in [ 60, 128, 1000 ]:
                    for ifg in [ 0, 24, 12 ]:
                        if maxp >= minp:
                            eq = all_mbw( bw, bfrq, minp, maxp, ifg, 8 )
                            if not eq:
                                print("bw:{} bfrq:{} minp:{} maxp:{} ifg:{}".format( bw, bfrq, minp, maxp, ifg ))



# -----
def calc_simulation_clock( hwconf, core_freq_reduction, verbose=False ):
    ################################
    # The clock periods need to be integers, and the absolute clock period is irrelevant
    # (since we do not run with timing).
    # The ratio of mac to core clock is important though, and therefore we
    # multiply the inverse of each frequencies with the product of the frequencies
    # (to get get the periods as integers), and then find the gcd and divide by that.
    core_reduced = hwconf.core_freq * core_freq_reduction
    def pdiv(x, y):
        """The code below seems to depend upon that a division is
        a floor division if both arguments are integers
        """
        if isinstance(x, int) and isinstance(y, int):
            return x // y
        return x / y

    # Assuming we stay below 1GHz and want a 1/1000000 precision: 
    mac_period = [ int(round(pdiv(1000000000, f))) for f in hwconf.mac_freq ]
    core_period = int(round(pdiv(1000000000, core_reduced)))
    conf_list = []
    conf_period = None
    master_period = None
    if hwconf.conf_clock_freq != None:
        conf_period = int(round(pdiv(1000000000, hwconf.conf_clock_freq)))
        conf_list = [conf_period]
    periods = mac_period+[core_period]+conf_list
    if hwconf.mult_base_freq:
        mult_period = int(round(pdiv(1000000000, (hwconf.mult_base_freq*core_freq_reduction))))
        periods += [mult_period]
    common = int(reduce(gcd, periods))
    core_period = core_period // common
    mac_period = [p // common for p in mac_period]
    if hwconf.mult_base_freq:
        master_period = mult_period // common
    if hwconf.conf_clock_freq != None:
        conf_period = conf_period // common
   
    if verbose:
        print("TB: core_freq", hwconf.core_freq)
        print("TB: core_freq_reduction", core_freq_reduction)
        print("TB: hwconf.mac_freq ", hwconf.mac_freq)
        print("TB: core_reduced ", core_reduced)
        print("TB: periods", periods)
        print("TB: gcd", common)
        print("TB: mac_period ", mac_period)
        print("TB: core_period ", core_period)
        if hwconf.mult_base_freq:
            print("TB: mult_period ", mult_period)

    return {
        'mac_period'    : mac_period,
        'core_period'   : core_period,
        'conf_period'   : conf_period,
        'master_period' : master_period
    }

# Calculate the packet sizes that will cause the PM to overflow, assuming the mac observes IFG
# For designs with RX halt this is not the proper function to use.
def pm_growth(
        min_pkt=60,
        max_pkt=1600,
        port_width=512,
        cell_size=1536,
        i2e_bytes=15,
        mac_freq=280.898876404,
        core_freq=280,
        port_bw=100000,
        ifg=192,
        port_ratio=0.33333):
    print(f"""pm_growth
    {min_pkt=}
    {max_pkt=}
    {port_width=}
    {cell_size=}
    {i2e_bytes=}
    {mac_freq=}
    {core_freq=}
    {port_bw=}
    {ifg=}
    {port_ratio=}
    """)
    ret = []
    for i in range(min_pkt, max_pkt):
        chunks = int(ceil(i*8.0 / port_width))
        sp_cells = int(ceil(i*8.0 / cell_size))
        pm_cells = int(ceil((i+i2e_bytes)*8.0 / cell_size))
        pktrate = port_bw/(i*8+192)
        if pm_cells>sp_cells:
            if min((mac_freq/chunks, pktrate))*pm_cells > core_freq*port_ratio:
                ret += [i]
    return ret

if __name__ == "__main__":
    import sys
    syntax = '''
Syntax: calculations.py type args
  type width:
    width [bw] [freq] [ifg]
    returns the needed bus width in bits
    bw:        The desired bandwidth in Mbits/s
    freq:      The frequency in MHz
    ifg:       The interframe gap + fcs in bits
  type freq:
    freq [bw] [bus_width] [ifg]
    returns the needed frequency
    bw:        The desired bandwidth in Mbits/s
    bus_width: The bus width in bits
    ifg:       The interframe gap + fcs in bits
  type minBusWidth:
    minBusWidth  bw bus_freq minPktBits maxPktBits ifg '''
    fail = False
    if len(sys.argv) == 1:
        fail = True
    elif sys.argv[1] == 'width':
        if len(sys.argv)!=5:
            print("Wrong number of arguments to width:", len(sys.argv) - 2)
            fail = True
        else:
            bw   = eval(sys.argv[2])
            freq = eval(sys.argv[3])
            ifg  = eval(sys.argv[4])
            print(macBusWidth(bw, freq, ifg=ifg))
            exit()
    elif sys.argv[1] == 'freq':
        if len(sys.argv)!=5:
            print("Wrong number of arguments to bus_width:", len(sys.argv) - 2)
            fail = True
        else:
            bw        = eval(sys.argv[2])
            bus_width = eval(sys.argv[3])
            ifg       = eval(sys.argv[4])
            freq = macBusFreq(bw, bus_width, ifg=ifg, quiet=1)
            print(freq)
            exit()
    elif sys.argv[1] == 'minBusWidth':
        if len(sys.argv)!=7:
            print("Wrong number of arguments to bus_width:", len(sys.argv) - 2)
            fail = True
        else:
            bw        = eval(sys.argv[2])
            bus_freq  = eval(sys.argv[3])
            minPkt    = eval(sys.argv[4])
            maxPkt    = eval(sys.argv[5])
            ifg       = eval(sys.argv[6])
            width = minBusWidth(bw, bus_freq, minPkt, maxPkt, ifg)
            print(width)
            exit()
    elif sys.argv[1] == 'macBusWidth':
        #(bw, freq, ifg=192, minPkt=480, maxPkt=1500*8, quiet=0, bus_alignment=1, packet_increment=8 ):
        if len(sys.argv)!=7:
            print("Wrong number of arguments to bus_width:", len(sys.argv) - 2)
            fail = True
        else:
            bw        = eval(sys.argv[2])
            bus_freq  = eval(sys.argv[3])
            minPkt    = eval(sys.argv[4])
            maxPkt    = eval(sys.argv[5])
            ifg       = eval(sys.argv[6])
            width = macBusWidth(bw=bw, freq=bus_freq, minPkt=minPkt*8, maxPkt=maxPkt*8, ifg=ifg)
            print(width)
            exit()
    elif sys.argv[1] == 'macBusFreq':
        #(bw, freq, ifg=192, minPkt=480, maxPkt=1500*8, quiet=0, bus_alignment=1, packet_increment=8 ):
        if len(sys.argv)!=7:
            print("Wrong number of arguments to bus_width:", len(sys.argv) - 2)
            fail = True
        else:
            bw        = eval(sys.argv[2])
            bus_width = eval(sys.argv[3])
            minPkt    = eval(sys.argv[4])
            maxPkt    = eval(sys.argv[5])
            ifg       = eval(sys.argv[6])
            freq = macBusFreq(bw=bw, width=bus_width, minPkt=minPkt*8, maxPkt=maxPkt*8, ifg=ifg)
            print(freq)
            exit()
    elif sys.argv[1] == 'pm_growth':
        #(bw, freq, ifg=192, minPkt=480, maxPkt=1500*8, quiet=0, bus_alignment=1, packet_increment=8 ):
        if len(sys.argv)!=10:
            print("Wrong number of arguments to bus_width:", len(sys.argv) - 2)
            fail = True
        else:
            min_pkt    = eval(sys.argv[2])
            max_pkt    = eval(sys.argv[3])
            port_width = eval(sys.argv[4])
            cell_size  = eval(sys.argv[5])
            i2e_bytes  = eval(sys.argv[6])
            port_bw    = eval(sys.argv[7])
            ifg        = eval(sys.argv[8])
            visit      = eval(sys.argv[9])
            sizes = pm_growth(min_pkt, max_pkt, port_width, cell_size, i2e_bytes)
            print(sizes)
            exit()
    elif sys.argv[1] == 'test':
        unittest()
    else:
        print("Unrecognized option \"%s\"" % sys.argv[1])
        fail = True

    if fail:
        print(syntax)
    exit()
