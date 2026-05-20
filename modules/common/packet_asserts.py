from myhdl import *
from modules.common.Common import copySignal, pass_through, multiflop, flop, sync_flop
from modules.conf import conf
from modules.conf.register import register
from modules.common.Common import hwdir
import sys
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
# TODO: A mode with latency 1, where all correct packets are forwarded.
# In the current version, if a first belonging to a valid packet that appears
# before the previous packet is done, both the interrupted packet and the
# interrupting packet are dropped. With a latency of 1 the valid, interrupting
# packet could go through.

def packet_asserts(
        first, last, valid_bytes, clk, rstn, cell_size, halt=None, port=None, assert_out=None, input_error=None, # input_error is combinatorical, to math the inputs.
        ofirst=None, olast=None, ovalid_bytes=None, oport=None, info=None, oinfo=None,
        request_address=None,
        request_data=None,
        request_id=None,
        request_type=None,
        request_re=None,
        request_we=None,
        reply_data=None,
        reply_id=None,
        reply_status=None,
        conf_clk=None,
        conf_rstn=None,
        bus_settings=None,
        ss_id=None,
        ss_max=None,
        consistency_check=0,
        assert_on_fail = 0,
        filter_errors = 0,
        nr_of_ports = None,
        max_bytes = None,
        doc_name = "",
        doc_index = None,
        cur_port = None,
        max_port = None,
        doc_attr = {},
        async_clock = False,
        name=""):
    if port is None:
        nr_of_ports = 1
        nr_of_ports_w = 1
        dest_port = 0
        portstring = ""
    else:
        assert nr_of_ports!=None, "ERROR! nr_of_ports need to be set when there is a port input to packet_asserts %s" % name
        nr_of_ports_w = (nr_of_ports-1).bit_length()
        dest_port = Signal(intbv(0)[nr_of_ports_w:])
        @always_comb
        def setdp():
            if port < nr_of_ports:
                dest_port.next = port[nr_of_ports_w:]
            else:
                dest_port.next = 0
        if port.max > nr_of_ports:
            @checker(clk.posedge, rstn.negedge)  # PALINT no_rstn
            def assertemptymask():
                if rstn==0:
                    pass
                else:
                    if port>=nr_of_ports:
                        if first!=0 or last!=0 or valid_bytes!=0:
                            print("ERROR! first %s last %s valid_bytes %s when port %s is above nr_of_ports %s in %s" % (first, last, valid_bytes, port, nr_of_ports))
                        
        portstring = "on port"
        if filter_errors==1:
            print("ERROR! %s packet_asserts cannot yet filter protocol errors on interfaces with more than one port!")
            assert False
                
        
    if async_clock:
        pstr = 'u'
        nr_sync_flops = hwconf.sync_flop_depth
        print(name, "async_clock set. Nr of sync flops", nr_sync_flops)        
    else:
        pstr = ''
        nr_sync_flops = 0
        print(name, "no async flops due to async_clock", async_clock)        

    debug_list = [first, last]
    debug_bits = hwconf.debug_read_width-2
    debug_desc = "1'last, 1'first\}"
    if port!=None:
        debug_list.append(port)
        debug_desc = str(len(port))+"'port, " + debug_desc
        debug_bits -= len(port)
    if halt!=None:
        debug_list.append(halt)
        debug_desc = str(len(halt))+"'halt, " + debug_desc
        debug_bits -= len(halt)
    debug_list.append(valid_bytes)
    if debug_bits < len(valid_bytes):
        debug_desc = str(debug_bits)+"'valid_bytes(truncated), "  + debug_desc
        debug_bits = 0
    else:
        debug_desc = str(len(valid_bytes))+"'valid_bytes, " + debug_desc
        debug_bits -= len(valid_bytes)
    debug_desc = name+" \{" + debug_desc
    debug = Signal(intbv(0)[hwconf.debug_read_width-debug_bits:0], debug_level=1, debug_descr=debug_desc)
    zPassdebug = pass_through(debug_list, debug, allow_mismatch=1, name=name+".zPassdebug")
    
    filtered_first = copySignal(first, t=modbv)
    filtered_last = copySignal(last, t=modbv)
    filtered_valid_bytes  = copySignal(valid_bytes, t=modbv)
        
    filtered_first_ff       = copySignal(first, t=modbv) # Not always used
    filtered_last_ff        = copySignal(last, t=modbv) # Not always used
    filtered_valid_bytes_ff = copySignal(valid_bytes, t=modbv) # not always used
    zFlopfirst = flop( filtered_first,  filtered_first_ff, clk, rstn, name=name+"+zFlopfirst")
    zFloplast = flop( filtered_last,  filtered_last_ff, clk, rstn, name=name+"+zFloplast")
    zFlopvalidbytes = flop( filtered_valid_bytes,  filtered_valid_bytes_ff, clk, rstn, name=name+"+zFlopvalidbytes")

    if reply_status!=None:
        reply_data_x   = copySignal(reply_data)
        reply_id_x     = copySignal(reply_id)
        reply_status_x = copySignal(reply_status)
        zFlopreplyd = multiflop(reply_data_x,   reply_data,   conf_clk, conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplyd") 
        zFlopreplyi = multiflop(reply_id_x,     reply_id,     conf_clk, conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplyi") 
        zFlopreplys = multiflop(reply_status_x, reply_status, conf_clk, conf_rstn, depth=hwconf.block_conf_flops, name=name+".zFlopreplys") 

    if False and filter_errors==1: # The short packets are dropped elsewhere, so this is correct.
        drop_short = 1
        assert max_bytes != None
    else:
        drop_short = 0
    drop_short_limit = hwconf.short_packet_limit
    
    nr_of_counters = 2
    if halt!=None:
        nr_of_counters += 1
    if drop_short:
        nr_of_counters += 1
    
    cw = hwconf.pkt_protocol_cnt_width
    if async_clock:
        halt_cnt  = Signal(modbv(0)[cw:])
        short_cnt = Signal(modbv(0)[cw:])
        pkt_cnt   = Signal(modbv(0)[cw:])
        error_cnt = Signal(modbv(0)[cw:])
    else:
        halt_cnt  = Signal(modbv(0)[cw:], debug_level=1)
        short_cnt = Signal(modbv(0)[cw:], debug_level=1)
        pkt_cnt   = Signal(modbv(0)[cw:], debug_level=1)
        error_cnt = Signal(modbv(0)[cw:], debug_level=1)
        
    short = Signal(modbv(0)[1:])
    print("packet_asserts %s ss_id, %s ss_max %s, cur_port %s, max_port %s, assert_on_fail %s, filter_errors %s, nr_of_ports %s" % (name, ss_id, ss_max, cur_port, max_port, assert_on_fail, filter_errors, nr_of_ports))
        
    if request_address!=None:
        if async_clock:        
            reg_write_data = [ Signal(modbv(0)[cw*nr_of_counters:], debug_level=1) ]
        else:
            reg_write_data = [ Signal(modbv(0)[cw*nr_of_counters:]) ]            
        reg_read_data = copySignal(reg_write_data)
        logic_one = Signal(modbv(1)[1:])
        cnt_list = [pkt_cnt, error_cnt]
        if halt!=None:
            cnt_list.append( halt_cnt )
        if drop_short:
            cnt_list.append( short_cnt )
        iAsyncFlopCnt = sync_flop(cnt_list, reg_write_data, conf_clk, conf_rstn, clk, rstn,
                                  nr_sync_flops, hwconf.sync_flop_mode, name=name+'.syncCnt')
        counter_table =  conf.CTable(
            name           = name+'.table',
            description    = 'Registers for reading the interface counters',
            regtype        = 'reg',
            fw_write_ports = 0,
            fw_read_ports  = 0
        )
        counter_reg =  conf.CRegister(
            doc_name  = doc_name,
            index = doc_index,
            doc_group = 'Statistics: Packet Datapath',
            name = f"rg_assert_counter_{doc_attr['name']}",
            description = 'Counters for the interface protocol checkers. The counters wrap. \\'+doc_attr['name'],
            doc_cur_ss = ss_id,
            doc_max_ss = ss_max,
            doc_cur_id = cur_port,
            doc_max_id = max_port,
            access = "r"+pstr,
            attributes = ['no_default_check', doc_attr],
            depth = 1)
        counter_field_pkt = conf.CField(
            name          = 'packets',
            short_name    = 'pkt',
            width         = cw,
            description   = 'Correct packets completed',
            default_value = 0,
            valid_data    = None,
            access        = 'r')
        counter_reg.append(counter_field_pkt)
        counter_field_error = conf.CField(
            name          = 'error',
            short_name    = 'err',
            width         = cw,
            description   = 'Bus protocol errors.',
            default_value = 0,
            valid_data    = None,
            access        = 'r')
        counter_reg.append(counter_field_error)
        if halt!=None:
            bridgestr = ""
            if hwconf.only_axis_mode:
                bridgestr = " on the internal interface between the switch and the AXI-streaming bridge"
            counter_field_halt = conf.CField(
                name          = 'halt',
                short_name    = 'hlt',
                width         = cw,
                description   = 'Halt errors. Incremented if first, last or valid_bytes%s is non-zero when halt is high.' % bridgestr,
                default_value = 0,
                valid_data    = None,
                access        = 'r')
            counter_reg.append(counter_field_halt)
        if drop_short:
            counter_field_short = conf.CField(
                name          = 'short',
                short_name    = 'srt',
                width         = cw,
                description   = 'Short packets dropped.',
                default_value = 0,
                valid_data    = None,
                access        = 'r')
            counter_reg.append(counter_field_short)
            
        counter_table.append(counter_reg)
        bus_settings.append(counter_table)
        iRegbank = register(
            request_address,
            request_data,
            request_id,
            request_type,
            request_re,
            request_we,
            reply_data_x,
            reply_id_x,
            reply_status_x,
            conf_clk, conf_rstn,
            counter_table,
            reg_read_data,
            reg_write_data,
            [1], # Data is already from flops, so no additional flop in the register
            name = name+".iRegbank")
        
    in_packet_flag = Signal(intbv(0)[nr_of_ports:0])
    in_packet_flag_ff = Signal(intbv(0)[nr_of_ports:0]) # Not always used
    error_out = Signal(intbv(0)[1:0])
    error = Signal(intbv(0)[1:0])
    assert_full_cell = Signal(intbv(0)[1:0])
    if assert_out!=None:
        @always_comb
        def driveassert():
            assert_out.next = error_out
    if input_error!=None:
        @always_comb
        def driveinerr():
            input_error.next = error
    if oport!=None:
        @always_comb
        def passport():
            oport.next = port
    if oinfo!=None:
        zFinfo = flop(info, oinfo, clk, rstn)

    # express mode should not use the normal packet error filter
    if filter_errors==1 and hwconf.express_mode ==0:
        @always_comb
        def driveo():
            if in_packet_flag_ff[dest_port]==1 and filtered_first==1 and filtered_last_ff==0:
                ofirst.next = 0
                ovalid_bytes.next = 0
                if filtered_first_ff==1:
                    olast.next = 0
                else:
                    olast.next = 1
            else:
                ofirst.next = filtered_first_ff
                olast.next = filtered_last_ff
                ovalid_bytes.next = filtered_valid_bytes_ff
    else:
        if ofirst!=None:
            zPassfirst = flop(first, ofirst, clk, rstn, name=name+"+zPassfirst")
        if olast!=None:
            zPasslast = flop(last, olast, clk, rstn, name=name+"+zPasslast")
        if ovalid_bytes!=None:
            zPassvalidbytes = flop(valid_bytes, ovalid_bytes, clk, rstn, name=name+"+zPassvalidbytes")

    begin_pkt = Signal(intbv(0)[1:0])
    abort_pkt = Signal(intbv(0)[1:0])

    above_short_limit = Signal(intbv(0)[1:0])
    if drop_short==1:
        if max_bytes <= drop_short_limit:
            @always_comb
            def setabovel():
                if last==1 and first==1:
                    above_short_limit.next = 0
                else:
                    above_short_limit.next = 1
        else:
            @always_comb
            def setabovel():
                if last==1 and first==1 and valid_bytes < drop_short_limit:
                    above_short_limit.next = 0
                else:
                    above_short_limit.next = 1
    else:
        @always_comb
        def setabovel():
            if last==1 and first==1 and valid_bytes > 0:
                above_short_limit.next = 1
            else:
                above_short_limit.next = 0
        
    @always_comb
    def filter():
        error.next = 0
        short.next = 0
        filtered_first.next = 0
        filtered_last.next = 0
        filtered_valid_bytes.next = 0

        if in_packet_flag[dest_port]==0:
            if first==1 and last==1 and above_short_limit==1:
                filtered_first.next = 1
                filtered_last.next = 1
                filtered_valid_bytes.next = valid_bytes
            elif first==1 and last==1:
                short.next = 1
            elif first==1 and last==0 and valid_bytes==(cell_size//8):
                filtered_first.next = 1
                filtered_last.next = 0
                filtered_valid_bytes.next = (cell_size//8)
            elif first==0 and last==0 and valid_bytes==0:
                pass
            else:
                error.next = 1
        elif in_packet_flag[dest_port]==1:
            if first==0 and last==0 and valid_bytes==(cell_size//8):
                filtered_valid_bytes.next = (cell_size//8)
            elif first==0 and last==1:
                filtered_first.next = 0
                filtered_last.next = 1
                filtered_valid_bytes.next = valid_bytes
            elif first==1 and (valid_bytes==(cell_size//8) or (above_short_limit==1 and last==1)):
                # A new packet before the old was ended.
                # The driveo process above will consume the previous cycle to terminate the
                # previous packet, so that the new can be passed on.
                filtered_first.next = 1
                filtered_last.next = last
                filtered_valid_bytes.next = valid_bytes
                error.next = 1
            elif first==1 and above_short_limit==0 and last==1:
                error.next = 1
                short.next = 1
            elif first==0 and last==0 and valid_bytes==0:
                pass
            else:
                error.next = 1

    halt_sig = Signal(intbv(0)[1:])
    check_halt = 0
    if halt!=None:
        check_halt = 1
        # zPasshalt = pass_through(halt, halt_sig, name=name+".Passhalt") # halt_sig width is wrong and this is not used
        
    @always(clk.posedge, rstn.negedge)
    def assertemptymask():
        if rstn==0:
            in_packet_flag.next = 0
            in_packet_flag_ff.next = 0
            error_cnt.next = 0
            halt_cnt.next  = 0
            short_cnt.next = 0
            error_out.next = 0
        else:
            if dest_port >= nr_of_ports:
                "synthesis translate_off"
                print("ERROR! %s dest_port %s >= nr_of_ports %s" % (name, dest_port, nr_of_ports))
                assert False
                "synthesis translate_on"
            in_packet_flag_ff.next = in_packet_flag
            if error==1:
                if assert_on_fail==1:
                    "synthesis translate_off"
                    print("%s protocol ERROR for port %s!" % ( name, dest_port ))
                    assert False
                    "synthesis translate_on"
                error_out.next = 1
                error_cnt.next = error_cnt + 1
            if short==1:
                short_cnt.next = short_cnt + 1
            if check_halt == 1:
                if halt==1 and (first==1 or last==1 or valid_bytes>0):
                    halt_cnt.next = halt_cnt+1
                    if assert_on_fail==1:
                        "synthesis translate_off"
                        print("%s halt protocol ERROR for port %s!" % ( name, dest_port ))
                        assert False
                        "synthesis translate_on"
            if filtered_first==1 and filtered_valid_bytes>0 and filtered_last==0:
                in_packet_flag.next[dest_port]  = 1
            if filtered_last==1:
                in_packet_flag.next[dest_port]  = 0
                    
            if consistency_check==1:
                "synthesis translate_off"
                print("Consistency check", name)
                if error_cnt>0 or halt_cnt>0:
                    print(name, "Consistency INFO. error_cnt = %s, halt_cnt = %s" % (error_cnt, halt_cnt)) 
                    assert False, ("%s: Consistency check FAILED!" % name)
                "synthesis translate_on"
            
    if olast==None:
        cntlast = filtered_last
    else:
        cntlast = olast
        
    @always(clk.posedge, rstn.negedge)
    def cntpkt():
        if rstn==0:
            pkt_cnt.next = 0
        else:
            if cntlast==1:
                pkt_cnt.next = pkt_cnt + 1
        
    return instances()
            
