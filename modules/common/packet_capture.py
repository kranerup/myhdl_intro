from myhdl import *
from modules.common.Common import copySignal, pass_through, multiflop, pipeline, pipeline_e, flop, request_bridge, reply_bridge, count_ones
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.common.Common import hwdir
import sys
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()

def packet_capture(
        first, last, valid_bytes, data, clk, rstn,
        request_address,
        request_data,
        request_id,
        request_type,
        request_re,
        request_we,
        reply_data,
        reply_id,
        reply_status,
        bus_settings,
        halt     = None, 
        error    = None,
        port     = None,
        nr_of_ports = 1,
        conf_clk = None,
        conf_rstn = None,
        ss_id    = None,
        doc_name = "",
        name=""):
        
    isasync = True
    cclk=conf_clk
    crstn=conf_rstn
    if conf_clk == None:
        cclk = clk
        crstn = rstn
        isasync = False
        
    # Method for growing the lists of conf signals when a new block configuration bus is added
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))
    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []        
        
    request_address_d = copySignal(request_address)
    request_data_d    = copySignal(request_data   )
    request_id_d      = copySignal(request_id     )
    request_type_d    = copySignal(request_type   )
    request_re_d      = copySignal(request_re     )
    request_we_d      = copySignal(request_we     )
    
    reply_data_x   = copySignal(reply_data)
    reply_id_x     = copySignal(reply_id)
    reply_status_x = copySignal(reply_status)

    # The bridges become transparent when the clocks are the same
    zReqbrigde = request_bridge(
        request_address,   request_data,   request_id,   request_type,   request_re,   request_we,
        request_address_d, request_data_d, request_id_d, request_type_d, request_re_d, request_we_d,
        cclk, clk, crstn, rstn, transparent=not isasync, name=name+".zReqbridge")
    zRepbrigde = reply_bridge(
        reply_data_x, reply_id_x, reply_status_x,
        reply_data,   reply_id,   reply_status,
        clk, cclk, rstn, crstn, transparent=not isasync, name=name+".zRepbridge")        

    depth = hwconf.packet_capture[doc_name]['depth']
    depth_w = (depth-1).bit_length()
    width = len(data)+len(valid_bytes) + 4
    max_lookahead  = 4 if port!=None else 0 
    if 'max_lookahead' in hwconf.packet_capture[doc_name]:
        max_lookahead  = hwconf.packet_capture[doc_name]['max_lookahead']
    max_lookbehind = 15 if port!=None else 0 
    if 'max_lookbehind' in hwconf.packet_capture[doc_name]:
        max_lookbehind = hwconf.packet_capture[doc_name]['max_lookbehind']

    if True:#error!=None:
        width += 1
        
    port_sig = 0
    if port!=None:
        width += len(port)
        port_sig = port
        
    print("packet_capture %s ss_id %s doc_name %s, depth=%s, width=%s, max_lookahead=%s, max_lookbehind=%s" % (name, ss_id, doc_name, depth, width, max_lookahead, max_lookbehind))
        

    #############################################################
    # The capture buffer
    mem_wdata = Signal(modbv(0)[width:])
    mem_waddr = Signal(intbv(0, min=0, max=depth))
    mem_wenable = Signal(modbv(0)[1:])
    
    mem_rdata = Signal(modbv(0)[width:])
    mem_raddr = Signal(intbv(0, min=0, max=depth))
    mem_renable = Signal(modbv(0)[1:])

    name_str = doc_name.replace("_", "")
    if max_lookahead>0:
        lookahead_str = " Capture can start before the trigger by setting a non-zero value in the lookahead register."
    else:
        lookahead_str = ""
    if max_lookbehind>0:
        lookbehind_str = " Capture will end after the end trigger if a non-zero value is setup in the lookbehind register."
    else:
        lookbehind_str = ""
        
    cMem = conf.CTable(
        name           = 'packet_capture_buffer_%s' %name_str,
        doc_name         = "Packet capture buffer %s" % name_str, 
        doc_group        = "Debug",
        description = (
            'Continous recording of the packet bus. Recording is triggered by signals indicated in the start register, and ended by the signals indicated in the end register.%s%s' % ( lookahead_str, lookbehind_str)),
        access         = 'r',
        attributes = ['no_random_check', 'no_default_check'],
        doc_cur_ss     = bus_settings.cur_ss,
        doc_max_ss     = bus_settings.max_ss,
        regtype        = 'mem')
    cRegInc = conf.CRegister(
        doc_name = "buffer",
        name = "buffer",
        index = "address",
        depth = depth,
    )
    cFieldInc = conf.CField(
        name = 'delimiter',
        width = 1,
        description = 'Indicates the start of a new capture window',
        default_value = 0)
    cRegInc.append(cFieldInc)
    cFieldInc = conf.CField(
        name = 'first',
        width = 1,
        description = 'first flag',
        default_value = 0)
    cRegInc.append(cFieldInc)
    cFieldInc = conf.CField(
        name = 'last',
        width = 1,
        description = 'last flag',
        default_value = 0)
    cRegInc.append(cFieldInc)
    cFieldInc = conf.CField(
        name = 'valid_bytes',
        width = len(valid_bytes),
        description = 'Valid bytes of data',
        default_value = 0)
    cRegInc.append(cFieldInc)
    cFieldInc = conf.CField(
        name = 'halt',
        width = 1,
        description = 'halt flag',
        default_value = 0)
    cRegInc.append(cFieldInc)
    if True:#error!=None:
        cFieldInc = conf.CField(
            name = 'error',
            width = 1,
            description = 'Protocol error',
            default_value = 0)
        cRegInc.append(cFieldInc)
    if port!=None:
        cFieldInc = conf.CField(
            name = 'port',
            width = len(port),
            description = 'port',
            default_value = 0)
        cRegInc.append(cFieldInc)
        
    cFieldInc = conf.CField(
        name = 'data',
        width = len(data),
        description = 'data bus',
        default_value = 0)
    cRegInc.append(cFieldInc)
    cMem.append(cRegInc)

    bus_settings.append(cMem)
    append_conf_signal() # Grow the conf reply lists
    doing_init = Signal(intbv(0)[1:])
    from modules.conf.mem_cpu_if import mem_cpu_if
    iBuffer = mem_cpu_if(
        request_address = request_address_d, 
        request_data    = request_data_d,   
        request_id      = request_id_d,     
        request_type    = request_type_d,   
        request_re      = request_re_d,     
        request_we      = request_we_d,     
        reply_data      = conf_reply_data[-1],
        reply_id        = conf_reply_id[-1],
        reply_status    = conf_reply_status[-1],
        doing_init      = doing_init,     
        clk             = clk,            
        rstn            = rstn,           
        settings        = cMem,       
        hw_idata        = mem_wdata,       
        hw_waddr        = mem_waddr,       
        hw_we           = mem_wenable,
        hw_odata        = mem_rdata,       
        hw_raddr        = mem_raddr,       
        hw_re           = mem_renable,
        input_flops     = 1,
        output_flops    = 1,
        name=name+'.iBuffer'         
    )
    
    FIRST  = 0
    HALT   = 1
    BUBBLE = 2
    ERROR  = 3
    if True:#error!=None:
        LAST   = 4
    else:
        LAST   = 3

    max_lookahead_w  = (max_lookahead).bit_length()
    max_lookbehind_w = (max_lookbehind).bit_length()
    max_len   = max_lookahead + max_lookbehind      
    max_len_w = (max_len).bit_length()
    max_cnt   = max_len*(LAST+1)
    max_cnt_w = (max_len).bit_length()

    conf_w = len(request_data)
    
    ##########################################################
    # The config regs
    conf_list = []
    cConf = conf.CTable(
        name           = 'packet_capture_settings_%s' %name_str,
        doc_name       = "Packet capture settings %s" % name_str, 
        doc_group      = "Debug",
        access         = 'rw',
        regtype = 'reg')
    
    cConfReg = conf.CRegister(
        doc_name = "Packet capture waddr %s" % name_str,
        doc_group = "Debug",
        name = "rg_pcap_waddr",
        attributes = ['no_default_check'],
        access = "r",
        depth = 1)
    cConfReg.append( conf.CField(
        name = 'waddr',
        width = depth_w,
        short_name = 'wa',
        description = '''Latest write address to the capture buffer''',        
        default_value = 0,
        valid_data = None) )
    c_waddr = cConfReg.fields[-1].get_signal()
    conf_list.append(c_waddr)
    cConf.append(cConfReg)
    
#    cConfReg = conf.CRegister(
#        doc_name = "Packet capture start counter %s" % name_str,
#        doc_group = "Debug",
#        name = "rg_pcap_cnt",
#        attributes = ['no_default_check'],
#        access = "r",
#        depth = nr_of_ports,
#        index = "port" if port!=None else None
#        )
#    cConfReg.append( conf.CField(
#        name = 'cnt',
#        width = depth_w,
#        description = '''Current number of start flags minus end flags''',        
#        default_value = 0,
#        valid_data = None) )
#    print "BABA: c_scnt", cConfReg.fields[-1].get_signal()
#    
#    c_scnt = [ cConfReg.fields[-1].get_signal() for _ in range(nr_of_ports) ] 
#    conf_list.extend(c_scnt)
#    cConf.append(cConfReg)
#    
    cConfReg = conf.CRegister(
        doc_name = "Packet capture start %s" % name_str,
        doc_group = "Debug",
        name = "rg_pcap_start",
        access = "rw",
        depth = 1)
    error_str=''
    if True:#error!=None:
        error_str = '  \\dscValue [bit %s] error' % ERROR
    cConfReg.append( conf.CField(
        name = 'start',
        width = 4,
        description = '''Start vector. Each set bit will trigger the start of a capture window.
\\begin{fieldValues}
  \\dscValue [bit 0] first
  \\dscValue [bit 1] halt
  \\dscValue [bit 2] bubble
%s
  \\dscValue [bit %s] last
\\end{fieldValues}''' % (error_str, LAST),        
        default_value = 1,
        valid_data = None) )
    c_start = cConfReg.fields[-1].get_signal()
    conf_list.append(c_start)
    cConf.append(cConfReg)
    
    cConfReg = conf.CRegister(
        doc_name = "Packet capture end %s" % name_str,
        doc_group = "Debug",
        name = "rg_pcap_end",
        access = "rw",
        depth = 1)
    
    cConfReg.append( conf.CField(
        name = 'end',
        width = 4,
        description = '''End vector. Each set bit will trigger the end of a capture window.
\\begin{fieldValues}
  \\dscValue [bit 0] first
  \\dscValue [bit 1] halt
  \\dscValue [bit 2] bubble
%s
  \\dscValue [bit %s] last
\\end{fieldValues}''' % (error_str, LAST),        
        default_value = 1,
        valid_data = None) )
    c_end = cConfReg.fields[-1].get_signal()
    conf_list.append(c_end)
    cConf.append(cConfReg)

    if max_lookahead > 0:
        cConfReg = conf.CRegister(
            doc_name = "Packet capture lookahead %s" % name_str,
            doc_group = "Debug",
            name = "rg_pcap_lookahead",
            access = "rw",
            depth = 1)
        cConfReg.append( conf.CField(
            name = 'lookahead',
            width = max_lookahead_w,
            description = (
                'A capture window will start this number of samples before the start trigger'
            ),        
            default_value = 4,
            valid_data = None) )
        c_lookahead = cConfReg.fields[-1].get_signal()
        conf_list.append(c_lookahead)
        cConf.append(cConfReg)
    else:
        c_lookahead = Signal(modbv(0)[1:])

    if max_lookbehind > 0:
        cConfReg = conf.CRegister(
            doc_name = "Packet capture lookbehind %s" % name_str,
            doc_group = "Debug",
            name = "rg_pcap_lookbehind",
            access = "rw",
            depth = 1)
        cConfReg.append( conf.CField(
            name = 'lookbehind',
            width = max_lookbehind_w,
            description = (
                'A capture window will end this number of samples after the end trigger'
            ),        
            default_value = 12,
            valid_data = None) )
        c_lookbehind = cConfReg.fields[-1].get_signal()
        conf_list.append(c_lookbehind)
        cConf.append(cConfReg)
    else:
        c_lookbehind = Signal(modbv(0)[1:])

    if port!=None:
        cConfReg = conf.CRegister(
            doc_name = "Packet capture port mask %s" % name_str,
            doc_group = "Debug",
            name = "rg_pcap_portmask",
            access = "rw",
            depth = 1)
        cConfReg.append( conf.CField(
            name = 'portmask',
            width = nr_of_ports,
            description = (
                'Data will only be captured from ports where the corresponing bit in this port mask is set.'
            ),        
            default_value = (1<<nr_of_ports)-1,
        valid_data = None) )
        c_portmask = cConfReg.fields[-1].get_signal()
        conf_list.append(c_portmask)
        cConf.append(cConfReg)
    else:
        cConfReg = conf.CRegister(
            doc_name = "Packet capture enable %s" % name_str,
            doc_group = "Debug",
            name = "rg_pcap_enable",
            access = "rw",
            depth = 1)
        cConfReg.append( conf.CField(
            name = 'enable',
            width = 1,
            description = (
                'Data will only be captured when the enable bit is set.'
            ),        
            default_value = 1,
        valid_data = None) )
        c_portmask = cConfReg.fields[-1].get_signal()
        conf_list.append(c_portmask)
        cConf.append(cConfReg)
    
    cConfReg = conf.CRegister(
        doc_name = "Packet capture misc %s" % name_str,
        doc_group = "Debug",
        name = "rg_pcap_misc",
        access = "rw",
        depth = 1)
    cConfReg.append( conf.CField(
        name = 'end_is_final',
        width = 2,
        description = (
            'The capture window can either be closed as soon as the end is triggered, '
            'or the number of start and end triggers are counted and '
            'the window is open when the number of starts exceeds the number of ends '
            'and closed when it does not'
            '\\begin{fieldValues}'
            '  \\dscValue [0] Default'
            '  \\dscValue [1] Use counters'
            '  \\dscValue [2] End is final'
            '\\end{fieldValues}'
            'The default setting for end_is_final is false whenever the below is true:'
            '(start[FIRST] + start[LAST] == end[FIRST] + end[LAST]) & '
            'start[HALT]   == end[HALT] & '
            'start[BUBBLE] == end[BUBBLE]'            
        ),        
        default_value = 0,
        valid_data = None) )
    c_end_is_final = cConfReg.fields[-1].get_signal()
    conf_list.append(c_end_is_final)
    cConf.append(cConfReg)

    END_DEFAULT = 0
    END_COUNT = 1
    END_FINAL = 2
    
    bus_settings.append(cConf)
    config_read  = cConf.get_all_signals()
    config_write = copySignal(config_read)

    start_cnt = [ Signal(modbv(0)[conf_w:]) for _ in range(nr_of_ports) ]
    start_cnt_max = (1<<conf_w)-1

    config_we = [ Signal(intbv(0)[1:]) for _ in range(len(config_write)) ]
    logic_high = Signal(intbv(1)[1:])
    zPasswaddrd = pass_through(mem_waddr,  config_write[0], name=name+".zPasswaddrd" )
    zPasswaddre = pass_through(logic_high, config_we[0],    name=name+".zPasswaddre" )
    zPassscntd = []
    zPassscnte = []
#    for i in range(nr_of_ports):
#        zPassscntd.append( pass_through(start_cnt[i],  config_write[1+i], name=name+".zPassscntd%s"%i ))
#        zPassscnte.append( pass_through(logic_high, config_we[1+i],    name=name+".zPasswcnte%s"%i ))
    
    append_conf_signal()
    iConf = register(
        request_address = request_address_d,
        request_data = request_data_d,
        request_id = request_id_d,
        request_type = request_type_d,
        request_re = request_re_d,
        request_we = request_we_d,
        reply_data = conf_reply_data[-1],
        reply_id = conf_reply_id[-1],
        reply_status = conf_reply_status[-1],
        clk = clk,
        rstn = rstn,
        settings = cConf,
        register_read  = config_read,
        register_we    = config_we,
        register_write = config_write,
        name = name+".iConf")
    zPassconf = pass_through(config_read, conf_list, name=name+".zPassconf")

    data_i = Signal(modbv(0)[width-1:])
    
    halt_sig = halt
    if halt==None:
        halt_sig = logic_zero
    if port!=None and halt!=None:
        halt_sig = Signal(modbv(0)[1:])
        @always_comb
        def sethalt():
            halt_sig.next = halt[port_sig]
            
    flat_list = [ first, last, valid_bytes, halt_sig ]
    error_val = Signal(modbv(0)[1:])
    if error!=None:
        error_val = error
    if True:#error!=None:
        flat_list.append(error_val)
    if port!=None:
        flat_list.append(port)
    flat_list.append(data)
    zFlatten = pass_through(flat_list, data_i, name=name+".zFlatten")
    data_d = [ copySignal(data_i) for _ in range(max_lookahead+1) ]
    data_dd = copySignal(data_i)
    iDelay = pipeline(data_i, data_d, clk=clk, rstn=rstn, name=name+".iDelay")
    
            
    @always_comb
    def setlookahead():
        data_dd.next = data_d[c_lookahead]

    in_packet = Signal(modbv(0)[nr_of_ports:])
    in_window = Signal(modbv(0)[nr_of_ports:])
    
    start_flag   = Signal(intbv(0, min=0, max=LAST+2))
    len_flag     = len(start_flag)
    end_flag     = Signal(intbv(0, min=0, max=LAST+2))
    end_flag_d   = [ [ Signal(intbv(0, min=0, max=LAST+2)) for _ in range(max_lookbehind+max_lookahead+2) ] for _ in range(nr_of_ports) ]
    if port==None:
        iDend = pipeline(end_flag, end_flag_d[0], clk=clk, rstn=rstn, name=name+".iDend")
    else:
        iDend = []
        end_enable = [ Signal(modbv(0)[1:]) for _ in range(nr_of_ports) ]
        for i in range(nr_of_ports):
            iDend.append(
                pipeline_e(
                    idata  = end_flag,
                    stage  = end_flag_d[i],
                    enable = end_enable[i],
                    clk    = clk,
                    rstn   = rstn,
                    name=name+".Dend%s"%i)
            )
        @always_comb
        def setenden():
            for i in range(nr_of_ports):
                end_enable[i].next = i==port_sig

    def setendd(end_flag, end_flag_d, end_flag_dd, delay):
        @always_comb
        def setendflag():
            if delay==0:
                end_flag_dd.next = end_flag
            else:
                end_flag_dd.next = end_flag_d[delay]
        return instances()

    iEndd = []
    end_flag_dd  = [ Signal(intbv(0, min=0, max=LAST+2)) for _ in range(nr_of_ports) ]
        
    end_delay = Signal(intbv(0, min=0, max=max_lookahead+max_lookbehind+2))
    @always_comb
    def setenddelay():
        end_delay.next = c_lookahead + c_lookbehind + 1
    for i in range(nr_of_ports):
        iEndd.append(
            setendd(end_flag, end_flag_d[i], end_flag_dd[i], end_delay)
        )
        
    end_is_final = Signal(intbv(0)[1:])
    
    start_sel = Signal(intbv(1<<FIRST)[LAST+1:])
    end_sel   = Signal(intbv(1<<FIRST)[LAST+1:])

    vector = Signal(intbv(0)[LAST+1:])
    svector = Signal(intbv(0)[LAST+1:])
    evector = Signal(intbv(0)[LAST+1:])
    
    logic_zero = Signal(intbv(0)[1:])
    bubble     = Signal(intbv(0)[1:])

    vector_list = [first, halt_sig, bubble]
    if True:#error!=None:
        vector_list.append(error_val)
    vector_list.append(last)
    
    zPassv = pass_through(vector_list, vector, name=name+".Passv")

    end_equal = Signal(intbv(1)[1:])
    if error!=None:
        @always_comb
        def setendequal():
            end_equal.next = c_start[ERROR] == c_end[ERROR]
    
    @always_comb
    def setisfinal():
        # When the number of start and end triggers are not equal
        # we cannot use counters to make sure the sampling is not stopped
        # prematurely, but must stop on every end flag
        if c_end_is_final==END_DEFAULT:
            if ( c_start[FIRST] + c_start[LAST] == c_end[FIRST] + c_end[LAST] and
                 c_start[HALT]   == c_end[HALT]   and
                 c_start[BUBBLE] == c_end[BUBBLE] and end_equal==1):
                end_is_final.next = 0
            else:
                end_is_final.next = 1
        elif c_end_is_final==END_COUNT:
            end_is_final.next = 0
        else:
            end_is_final.next = 1
            
    @always_comb
    def setbubble():
        bubble.next = in_packet[port_sig]==1 and valid_bytes==0
        svector.next = vector & c_start
        evector.next = vector & c_end
        
    @always_comb
    def setstart():
        start_flag.next = count_ones(svector, w=len_flag)
            
    @always_comb
    def setend():
        end_flag.next = count_ones(evector, w=len_flag)

    last_hit = Signal(modbv(0)[nr_of_ports:])
    @always(clk.posedge, rstn.negedge)
    def pcapwrite():
        if rstn==0:
            for i in range(nr_of_ports):
                start_cnt[i].next = 0
            in_packet.next = 0
            in_window.next = 0
            mem_waddr.next = depth-1
            mem_wenable.next = 0
            mem_wdata.next = 0
            last_hit.next = 0
        else:
            next_start_cnt = intbv(0, min=-2*(LAST+3), max=start_cnt_max+2*(LAST+3))
            next_start_cnt[:] = start_cnt[port_sig] + start_flag - end_flag_dd[port_sig]
            if next_start_cnt < 0:
                next_start_cnt[:] = 0
            elif next_start_cnt > start_cnt_max:
                next_start_cnt[:] = start_cnt_max
            next_in_window = modbv(0)[1:]
            next_hit = modbv(0)[1:]
            delimiter = modbv(0)[1:]
            if end_is_final==0:
                next_in_window[:] = 0
                next_hit[:] = start_flag > 0
                start_cnt[port_sig].next = next_start_cnt
                if next_start_cnt > 0:
                    next_in_window[:] = 1
            else:
                next_in_window[:] = in_window
                next_hit[:]       = start_flag>0
                if start_flag>0 and end_flag_dd[port_sig]==0:
                    next_in_window[:] = 1
                elif end_flag_dd[port_sig]>0:
                    next_in_window[:] = 0
            in_window.next[port_sig] = next_in_window
            last_hit.next[port_sig] = next_hit
            
            mem_wenable.next = 0
            mem_wdata.next   = 0
            if first==1:
                in_packet.next[port_sig] = 1
            if last==1:
                in_packet.next[port_sig] = 0
            if next_hit==1 and in_window[port_sig]==0 and last_hit[port_sig]==0:
                delimiter[:] = 1
            if (next_in_window==1 or next_hit==1 or in_window[port_sig]==1) and c_portmask[port_sig]==1:
                if mem_waddr==depth-1:
                    mem_waddr.next = 0
                else:
                    mem_waddr.next = mem_waddr+1
                mem_wenable.next = 1
                mem_wdata.next = concat(data_dd, delimiter)

    iCollector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data_x, reply_id_x, reply_status_x, clk, rstn, bus_settings, name = name+'.iCollector')
                
    return instances()
            
