from myhdl import *
from modules.common.Common import copySignal, compoundWidth, pass_through, flop, signalType
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.common.Common import multiflop, pipe_request, sync_flop
from .pkt_edge_conf import pkt_edge_conf
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


def pkt_edge_statistics(
        # Packet interface
        ivalid_bytes,ifirst,ilast,
        pcnt_edge,
        # Conf interface
        request_address, request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,bus_settings,
        clk_pkt, rstn_pkt,
        clk_conf = None,
        rstn_conf = None,
        iport = None,
        doc_pos = "",
        name = ""):

    print("pkt_edge_statistics %s: clk=%s" % (name, clk_pkt))
    if iport==None:
        print("Warning! TODO: pkt_edge_statstics does not support iport==None yet. Please fix that.")

    isasync = True
    local_conf_clk = clk_conf
    local_conf_rstn = rstn_conf
    if clk_conf == None:
        local_conf_clk  = clk_pkt
        local_conf_rstn = rstn_pkt
        isasync = False
        print("ERROR! edge_statistics only works under isasync mode. Need to add a new core clk for mixed speed designs!")
        assert False

    short_packet_limit = hwconf.short_packet_limit

    conf_width = hwconf.conf_data_width
    
    nr_of_ports = hwconf.nr_of_ports

    length_ref_conf = [ Signal(intbv(0)[conf_width:0])  for _ in range(nr_of_ports)]
    short_cnt_conf = [ Signal(intbv(0)[conf_width:0]) for _ in range(nr_of_ports)]
    long_cnt_conf  = [ Signal(intbv(0)[conf_width:0]) for _ in range(nr_of_ports)]
    byte_cnt_conf  = [ Signal(intbv(0)[conf_width:0]) for _ in range(nr_of_ports)]

    ivalid_bytes_ff = copySignal(ivalid_bytes) 

    ifirst_ff = copySignal(ifirst)     
    
    ilast_ff = copySignal(ilast) 

    pcnt_edge_ff = copySignal(pcnt_edge) 
    
    if pcnt_edge != None:
        zFlopedg = multiflop( pcnt_edge, pcnt_edge_ff, local_conf_clk, local_conf_rstn, depth=hwconf.pcnt_flops, name=name+".zFlopedg")
            
    request_address_d = copySignal(request_address)
    request_data_d    = copySignal(request_data   )
    request_id_d      = copySignal(request_id     )
    request_type_d    = copySignal(request_type   )
    request_re_d      = copySignal(request_re     )
    request_we_d      = copySignal(request_we     )
    zpr = pipe_request(request_address,   request_data,   request_id,   request_type,   request_re,   request_we,
                       request_address_d, request_data_d, request_id_d, request_type_d, request_re_d, request_we_d,
                       local_conf_clk, local_conf_rstn, depth=hwconf.block_conf_flops, name=name+".pr")

    reply_data_x   = copySignal(reply_data)
    reply_id_x     = copySignal(reply_id)
    reply_status_x = copySignal(reply_status)
    zFlopreplyd = multiflop(reply_data_x,   reply_data,   local_conf_clk, local_conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplyd") 
    zFlopreplyi = multiflop(reply_id_x,     reply_id,     local_conf_clk, local_conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplyi") 
    zFlopreplys = multiflop(reply_status_x, reply_status, local_conf_clk, local_conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplys") 

    InstEdgeConf = pkt_edge_conf(
        from_conf_length_ref = length_ref_conf,
        to_conf_short_cnt    = short_cnt_conf,
        to_conf_long_cnt     = long_cnt_conf,
        to_conf_byte_cnt     = byte_cnt_conf,
        pcnt_edge            = pcnt_edge_ff,
        request_address      = request_address_d,
        request_data         = request_data_d,
        request_id           = request_id_d,
        request_type         = request_type_d,
        request_re           = request_re_d,
        request_we           = request_we_d,
        reply_data           = reply_data_x,
        reply_id             = reply_id_x,
        reply_status         = reply_status_x,
        bus_settings         = bus_settings,
        clk                  = local_conf_clk,
        rstn                 = local_conf_rstn,
        doc_pos              = doc_pos,
        conf_width           = conf_width,
        isasync                = isasync,
        name                 = name+".edgeconf")


    InstEdgeCnt = []
    zFlopfir  = []
    zFlopvb   = []
    zFloplas  = []
    print("DB---", nr_of_ports, len(ifirst), len(ifirst_ff))
    for i in range(nr_of_ports):
        if signalType(clk_pkt):
            clk_for_mac = clk_pkt
            rstn_for_mac = rstn_pkt
        else:
            clk_for_mac = clk_pkt[i]
            rstn_for_mac = rstn_pkt[i]
        
        zFlopfir.append(multiflop( ifirst[i], ifirst_ff[i], clk_for_mac, rstn_for_mac, depth=hwconf.block_input_flops+hwconf.top_channel_flops, name=name+".zFlopfir"))
        zFlopvb.append(multiflop( ivalid_bytes[i], ivalid_bytes_ff[i], clk_for_mac, rstn_for_mac, depth=hwconf.block_input_flops+hwconf.top_channel_flops, name=name+".zFlopvb"))
        zFloplas.append(multiflop( ilast[i], ilast_ff[i], clk_for_mac, rstn_for_mac, depth=hwconf.block_input_flops+hwconf.top_channel_flops, name=name+".zFloplas"))
        
        InstEdgeCnt.append(pkt_edge_counter(
            ivalid_bytes   = ivalid_bytes_ff[i],
            ifirst         = ifirst_ff[i],
            ilast          = ilast_ff[i],
            length_ref_conf = length_ref_conf[i],
            short_cnt_conf = short_cnt_conf[i],
            long_cnt_conf  = long_cnt_conf[i],
            byte_cnt_conf  = byte_cnt_conf[i],
            clk_pkt        = clk_for_mac,
            clk_conf       = local_conf_clk,
            rstn_pkt       = rstn_for_mac,
            rstn_conf      = local_conf_rstn,
            conf_width     = conf_width,
            isasync          = isasync,
            name           = name+".edgeCnt%d"%i))

    return instances()

def pkt_edge_counter(
        ivalid_bytes,ifirst,ilast,
        length_ref_conf,
        short_cnt_conf,
        long_cnt_conf,
        byte_cnt_conf,
        clk_conf,clk_pkt,
        rstn_conf,rstn_pkt,
        conf_width = 24,
        isasync = False,
        name=""):


    short_cnt      = Signal(modbv(0)[conf_width:0])
    short_cnt_next = Signal(modbv(0)[conf_width:0])
    short_cnt_dd   = Signal(modbv(0)[conf_width:0])
    long_cnt       = Signal(modbv(0)[conf_width:0])
    long_cnt_next  = Signal(modbv(0)[conf_width:0])
    long_cnt_dd    = Signal(modbv(0)[conf_width:0])
    byte_cnt      = Signal(modbv(0)[conf_width:0])
    byte_cnt_next = Signal(modbv(0)[conf_width:0])
    byte_cnt_dd   = Signal(modbv(0)[conf_width:0])
    
    current_length = Signal(modbv(0)[conf_width:0])
    pkt_length  = Signal(modbv(0)[conf_width:0])
    count_flag = Signal(modbv(0)[1:0])

    length_ref  = copySignal(length_ref_conf)
    
    @always(clk_pkt.posedge, rstn_pkt.negedge)
    def currentLength():
        if rstn_pkt==0:
            current_length.next = 0
        else:
            if ifirst==1:
                current_length.next = ivalid_bytes
            else:
                current_length.next = current_length+ivalid_bytes

    @always(clk_pkt.posedge, rstn_pkt.negedge)
    def pktLength():
        if rstn_pkt==0:
            pkt_length.next = 0
            count_flag.next = 0
        else:
            if ilast==1:
                pkt_length.next = current_length+ivalid_bytes
                count_flag.next = 1
            else:
                pkt_length.next = 0
                count_flag.next = 0

    @always_comb
    def pktcnt():
        short_cnt_next.next = short_cnt
        long_cnt_next.next = long_cnt
        if count_flag == 1:
            if pkt_length >= length_ref:
                long_cnt_next.next = long_cnt+1
            else:
                short_cnt_next.next = short_cnt+1

    @always(clk_pkt.posedge, rstn_pkt.negedge)
    def cntreg():
        if rstn_pkt==0:
            short_cnt.next = 0
            long_cnt.next = 0
            byte_cnt.next = 0
        else:
            short_cnt.next = short_cnt_next
            long_cnt.next = long_cnt_next
            if ivalid_bytes>0:
                byte_cnt.next = byte_cnt + ivalid_bytes
    zps = []
    if isasync:
        # Synchronize to conf clk
        zFlopasync = sync_flop([long_cnt, short_cnt, byte_cnt],
                               [long_cnt_conf, short_cnt_conf, byte_cnt_conf],
                               clk_conf, rstn_conf, clk_pkt, rstn_pkt,
                               hwconf.sync_flop_depth, hwconf.sync_flop_mode, name=name+".zFlopasync")
        zFlopRef   = sync_flop(length_ref_conf, length_ref, clk_pkt, rstn_pkt,
                               clk_conf, rstn_conf,
                               hwconf.sync_flop_depth, hwconf.sync_flop_mode, name=name+'.zLengthRef')
    else:
        zPasscnf = pass_through([long_cnt, short_cnt, byte_cnt], [long_cnt_conf, short_cnt_conf, byte_cnt_conf], name=name+".zPasscnf")
    
    return instances()
