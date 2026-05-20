from myhdl import *
from modules.common.Common import copySignal, compoundWidth, pass_through, flop
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


def pkt_edge_conf(
        # Internal interface
        from_conf_length_ref,
        to_conf_short_cnt,
        to_conf_long_cnt,
        to_conf_byte_cnt,
        pcnt_edge,
        # Conf interface
        request_address, request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,bus_settings,
        clk,
        rstn,
        doc_pos = "",
        conf_width = 24,
        isasync=False,
        name = ""):


    nr_of_ports = hwconf.nr_of_ports

    short_packet_limit = hwconf.short_packet_limit

    if 'RX' in doc_pos:
        doc_index = 'Ingress Port'
        doc_attr = {'block':'sp_len','name':'rxPktLen'}
    elif 'TX' in doc_pos:
        doc_index = 'Egress Port'
        doc_attr = {'block':'ps_len','name':'txPktLen'}
    else:
        print("PKT_EDGE ERROR! Wrong doc_pos", doc_pos)
        assert False

    if isasync:
        pstr='u'
    else:
        pstr=''

    logic_high = Signal(intbv(1)[1:0])
    pcnt_sync  = Signal(intbv(0)[1:0])
    if pcnt_edge == None:
        zPsPcnt = pass_through(logic_high, pcnt_sync, name=name+'.psCntEdge')
    else:
        zPsPcnt = pass_through(pcnt_edge, pcnt_sync, name=name+'.psCntEdge')

    
# Conf Interface Setup
    # Method for growing the lists of conf signals when a new block configuration bus is added 
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))

    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
  

    # Conf interface
    ref_register_read_data    = []
    ref_register_write_data   = []
    ref_register_write_enable = []
    zps     = []
    # Set up the packet counter register
    pkt_ref_regbank_settings = conf.CTable(name        =  'pkt_ref_'+name,
                                           description =  'Register bank for packet reference in '+doc_pos,
                                           regtype     =  'reg',
                                           fw_write_ports  = 0,
                                           fw_read_ports   = 0)
    

    for i in range(nr_of_ports):
        pkt_ref_field_settings  = conf.CField(
            name           = 'bytes',
            width          = conf_width,
            description    = 'Number of bytes',
            short_name     = 'cnt',
            default_value  = short_packet_limit,
            valid_data     = None)
        pkt_ref_register_settings = conf.CRegister(
            doc_name       = doc_pos+' Packet Length Divide',
            doc_group      = "Global Configuration",
            description    = 'Packets with length below this value are counted in \\register{%s Packets in Length Group S}, otherwise in \\register{%s Packets in Length Group L}. The value shall not be updated with ongoing traffic.'%(doc_pos, doc_pos),
            name           = 'rg_length_ref_p'+str(i),
            index          = doc_index,
            doc_cur_id     = i,
            doc_max_id     = nr_of_ports,
            access         = 'rw'+pstr,
            depth          = 1)
        pkt_ref_register_settings.append(pkt_ref_field_settings)
        pkt_ref_regbank_settings.append(pkt_ref_register_settings)

        ref_register_read_data.append(Signal(intbv(0)[conf_width:0]))
        ref_register_write_data.append(Signal(intbv(0)[conf_width:0]))
        ref_register_write_enable.append(Signal(intbv(0)[1:0]))
        zps.append(pass_through(ref_register_read_data[-1], from_conf_length_ref[i], name=name+".refg"))


    bus_settings.append(pkt_ref_regbank_settings)
    append_conf_signal() # Grow the conf reply lists
    InstPktRefRegbank = register(
        request_address = request_address,
        request_data    = request_data,
        request_id      = request_id,
        request_type    = request_type,
        request_re      = request_re,
        request_we      = request_we,
        reply_data      = conf_reply_data[-1],
        reply_id        = conf_reply_id[-1],
        reply_status    = conf_reply_status[-1],
        clk             = clk,
        rstn            = rstn,
        settings        = pkt_ref_regbank_settings,
        register_read   = ref_register_read_data,
        register_write  = ref_register_write_data,
        register_we     = ref_register_write_enable,
        name            = name +'CPURegister_pkt_ref')
    
    

    # Set up short packet counter
    # Conf interface
    short_register_read_data    = []
    short_register_write_data   = []
    short_register_write_enable = []

    short_counter_regbank_settings = conf.CTable(name        =  'short_pkt_'+name,
                                                 description =  'Register bank for short packet counters in '+doc_pos,
                                                 regtype     =  'reg',
                                                 fw_write_ports  = 0,
                                                 fw_read_ports   = 0)

    for i in range(nr_of_ports):

        short_counter_field_settings  = conf.CField(
            name           = 'packets',
            width          = conf_width,
            description    = 'Number of packets',
            short_name     = 'cnt',
            default_value  = 0,
            valid_data     = None)
        short_counter_register_settings = conf.CRegister(
            doc_name       = doc_pos+' Packets in Length Group S',
            doc_group      = "Statistics: Packet Datapath",            
            description    = 'Number of packets with length below the measurement reference in \\register{%s Packet Length Divide}. \\'%doc_pos+doc_attr['name'],
            name           = 'rg_count_pkt_short'+str(i),
            attributes     = ['no_default_check', doc_attr],
            index          = doc_index,            
            doc_cur_id     = i,
            doc_max_id     = nr_of_ports,
            access         = 'r'+pstr, # Read only
            depth          = 1)
        short_counter_register_settings.append(short_counter_field_settings)
        short_counter_regbank_settings.append(short_counter_register_settings)

        short_register_read_data.append(Signal(intbv(0)[conf_width:0]))
        short_register_write_data.append(Signal(intbv(0)[conf_width:0]))
        short_register_write_enable.append(Signal(intbv(0)[1:0]))
        zps.append(pass_through(to_conf_short_cnt[i], short_register_write_data[-1], name=name+".we1"))
        zps.append(pass_through(pcnt_sync, short_register_write_enable[-1], name=name+".we2"))

    bus_settings.append(short_counter_regbank_settings)
    append_conf_signal() # Grow the conf reply lists    
    InstShortPktRegbank = register(request_address = request_address,
                                   request_data    = request_data,
                                   request_id      = request_id,
                                   request_type    = request_type,
                                   request_re      = request_re,
                                   request_we      = request_we,
                                   reply_data      = conf_reply_data[-1],
                                   reply_id        = conf_reply_id[-1],
                                   reply_status    = conf_reply_status[-1],
                                   clk             = clk,
                                   rstn            = rstn,
                                   settings        = short_counter_regbank_settings,
                                   register_read   = short_register_read_data,
                                   register_write  = short_register_write_data,
                                   register_we     = short_register_write_enable,
                                   name            = name +'CPURegister_pkt_short_counter')
    
    



    # Set up long packet counter
    # Conf interface
    long_register_read_data    = []
    long_register_write_data   = []
    long_register_write_enable = []
    
    long_counter_regbank_settings = conf.CTable(
        name        =  'long_pkt_'+name,
        description =  'Register bank for long packet counters in '+doc_pos,
        regtype     =  'reg')
    
    for i in range(nr_of_ports):
        long_counter_field_settings  = conf.CField(
            name           = 'packets',
            width          = conf_width,
            description    = 'Number of packets',
            short_name     = 'cnt',
            default_value  = 0,
            valid_data     = None)
        long_counter_register_settings = conf.CRegister(
            doc_name       = doc_pos+' Packets in Length Group L',
            doc_group      = "Statistics: Packet Datapath",
            description    = 'Number of packets with length below the measurement reference in \\register{%s Packet Length Divide}. \\'%doc_pos+doc_attr['name'],
            name           = 'rg_count_pkt_long'+str(i),
            attributes     = ['no_default_check', doc_attr],
            index          = doc_index,
            doc_cur_id     = i,
            doc_max_id     = nr_of_ports,
            access         = 'r'+pstr, # Read only
            depth          = 1)
        long_counter_register_settings.append(long_counter_field_settings)
        long_counter_regbank_settings.append(long_counter_register_settings)

        long_register_read_data.append(Signal(intbv(0)[conf_width:0]))
        long_register_write_data.append(Signal(intbv(0)[conf_width:0]))
        long_register_write_enable.append(Signal(intbv(0)[1:0]))
        zps.append(pass_through(to_conf_long_cnt[i], long_register_write_data[-1], name=name+".we3"))
        zps.append(pass_through(pcnt_sync, long_register_write_enable[-1], name=name+".we4"))
    
    bus_settings.append(long_counter_regbank_settings)
    append_conf_signal() # Grow the conf reply lists    
    InstLongPktRegbank = register(
        request_address = request_address,
        request_data    = request_data,
        request_id      = request_id,
        request_type    = request_type,
        request_re      = request_re,
        request_we      = request_we,
        reply_data      = conf_reply_data[-1],
        reply_id        = conf_reply_id[-1],
        reply_status    = conf_reply_status[-1],
        clk             = clk,
        rstn            = rstn,
        settings        = long_counter_regbank_settings,
        register_read   = long_register_read_data,
        register_write  = long_register_write_data,
        register_we     = long_register_write_enable,
        name            = name +'CPURegister_pkt_logn_counter')
    

    # Set up byte counter
    # Conf interface
    byte_register_read_data    = []
    byte_register_write_data   = []
    byte_register_write_enable = []
    
    byte_counter_regbank_settings = conf.CTable(
        name        =  'byte_pkt_'+name,
        description =  'Register bank for byte counters in '+doc_pos,
        regtype     =  'reg')
    
    for i in range(nr_of_ports):
        byte_counter_field_settings  = conf.CField(
            name           = 'packets',
            width          = conf_width,
            description    = 'Number of bytes',
            short_name     = 'cnt',
            default_value  = 0,
            valid_data     = None)
        byte_counter_register_settings = conf.CRegister(
            doc_name       = doc_pos+' Total Number of Bytes',
            doc_group      = "Statistics: Packet Datapath",
            description    = 'Number of bytes.',
            name           = 'rg_count_bytes_'+str(i),
            attributes     = ['no_default_check', doc_attr],
            index          = doc_index,
            doc_cur_id     = i,
            doc_max_id     = nr_of_ports,
            access         = 'r'+pstr, # Read only
            depth          = 1)
        byte_counter_register_settings.append(byte_counter_field_settings)
        byte_counter_regbank_settings.append(byte_counter_register_settings)

        byte_register_read_data.append(Signal(intbv(0)[conf_width:0]))
        byte_register_write_data.append(Signal(intbv(0)[conf_width:0]))
        byte_register_write_enable.append(Signal(intbv(0)[1:0]))
        zps.append(pass_through(to_conf_byte_cnt[i], byte_register_write_data[-1], name=name+".we3"))
        zps.append(pass_through(pcnt_sync, byte_register_write_enable[-1], name=name+".we4"))
    
    bus_settings.append(byte_counter_regbank_settings)
    append_conf_signal() # Grow the conf reply lists    
    InstBytePktRegbank = register(
        request_address = request_address,
        request_data    = request_data,
        request_id      = request_id,
        request_type    = request_type,
        request_re      = request_re,
        request_we      = request_we,
        reply_data      = conf_reply_data[-1],
        reply_id        = conf_reply_id[-1],
        reply_status    = conf_reply_status[-1],
        clk             = clk,
        rstn            = rstn,
        settings        = byte_counter_regbank_settings,
        register_read   = byte_register_read_data,
        register_write  = byte_register_write_data,
        register_we     = byte_register_write_enable,
        name            = name +'.CPURegister')
    

    

    collector = conf_bus_collector(
        conf_reply_data,
        conf_reply_id,
        conf_reply_status,
        reply_data,
        reply_id,
        reply_status,
        clk, rstn,
        bus_settings,
        name = name+'.collector')

    

    return instances()
