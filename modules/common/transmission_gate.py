from myhdl import *
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.conf.mem_cpu_if import mem_cpu_if
from modules.common.Common import copySignal, pass_through, listType, flop, multiflop
import math

import sys
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


def gate_control(
        igate_id,  # In
        ogate_addr, # Out
        ogate_en,   # Out
        request_address, request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,bus_settings,
        tick,
        clk,
        rstn,
        nr_of_lists,
        gate_list_depth,
        gate_type,
        ss_id,
        name = ''
    ):


    mem_read_latency = 1+hwconf.memory_input_flops+hwconf.memory_output_flops    
    
    if gate_type == "Ingress":
        regstr = 'ingress'
        status_w = 1
        list_index = "Ingress Gate ID"
        status_des = "ingress streams"
        status_field_name = "gateStatus"
        output_latency = mem_read_latency
    elif gate_type == "Egress":
        regstr = 'egress'
        status_w = max(hwconf.queue_max)
        list_index = "Egress Port"
        status_des = "egress queues"
        status_field_name = "disableQueueMask"
        output_latency = 0 # Egress has fixed order of selected igate_id (port number)
    else:
        print("%s ERROR! Unknown transmission gate type"%name)
        assert False
    

    nr_of_ticks  = hwconf.tick['nr_of_ticks']
    ticks_w       = (nr_of_ticks-1).bit_length()
    tick_cnt_w    = 64 # This size guarantees no wrap around in real world

    gate_list_w   = (gate_list_depth-1).bit_length()


    enable     = [Signal(intbv(0)[1:0])  for  _ in range(nr_of_lists)]
    enable_d1  = [Signal(intbv(0)[1:0])  for  _ in range(nr_of_lists)]    
    start_addr = [Signal(modbv(0)[gate_list_w:0])  for _ in range(nr_of_lists)]
    end_addr   = [Signal(modbv(0)[gate_list_w:0])  for _ in range(nr_of_lists)]    
    cur_addr   = [Signal(modbv(0)[gate_list_w:0])  for _ in range(nr_of_lists)]
    gate_depth = [Signal(modbv(0)[gate_list_w:0])  for _ in range(nr_of_lists)]
    tick_nr    = [Signal(modbv(0)[ticks_w:0])  for _ in range(nr_of_lists)]
    max_tick   = [Signal(modbv(0)[tick_cnt_w:0]) for _ in range(nr_of_lists)]

    new_start  = copySignal(enable)

    tick_cnt   = copySignal(max_tick)
    tick_cnt_next = copySignal(max_tick)

# -- Setup CPU register: egress transmission gate


    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
    # Method for growing the lists of conf signals when a new block configuration bus is added 
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))
    

    conf_config_read = []
    cBankGateSet = conf.CTable(
        name = "regbank_%s_gate%s"%(regstr, ss_id),
        description = "",
        regtype = "reg")
    for i in range(nr_of_lists):
        cRegGateSet = conf.CRegister(
            doc_name  = "%s Transmission Gate Configuration"%gate_type,
            doc_group = "Transmission Gates",
            description = "Setup the start address, end address and time intervals when lookup in the \\register{%s Transmission Gate List}. The walkthrough of the gate list is repeated from the start address till the end address. Before configuring other fields in this register,the enable field shall be set to 0 to insure accurate time measurement. "%gate_type,
            name  = 'rg_%sGateConfig_'%regstr+str(i),
            index = list_index,
            doc_cur_id = i,
            doc_max_id = nr_of_lists-1,
            doc_cur_ss     = bus_settings.cur_ss,
            doc_max_ss     = bus_settings.max_ss,
            access = 'rw', # Read and write
            depth = 1)

        cRegGateSet.append(conf.CField(
            name   = "enable",
            width  = 1,
            default_value = 0,
            description = "If set, transmission gate for this %s is enabled."%list_index.lower()))

        cRegGateSet.append(conf.CField(
            name   = "startAddr",
            width  = gate_list_w,
            description = "Start address of the gate in the \\register{%s Transmission Gate List}. "%gate_type))

        cRegGateSet.append(conf.CField(
            name   = "endAddr",
            width  = gate_list_w,
            description = "End address of the gate in the \\register{%s Transmission Gate List}. "%gate_type))

        cRegGateSet.append(conf.CField(
            name          = 'tick',
            width         = ticks_w,
            description   = 'Select one of the %d available ticks for time measurement. The tick frequencies are configured globaly in the PTP Tick Configuration register.' % (hwconf.tick['nr_of_ticks'])))

        cRegGateSet.append(conf.CField(
            name          = 'maxTick',
            width         = tick_cnt_w,
            default_value = 20,
            description   = 'Number of ticks (see Chapter \\hyperref[chap:Tick]{Tick}) between scheduled gate list.'))


        cBankGateSet.append(cRegGateSet)
        conf_config_read.append(Signal(intbv(0)[gate_list_w*2+1+ticks_w+tick_cnt_w:0]))
        
    bus_settings.append(cBankGateSet)
    append_conf_signal() # Grow the conf reply lists to accomodate the disable_queue_output regbank
    iGateSet = register(
        request_address,
        request_data,
        request_id,
        request_type,
        request_re,
        request_we,
        conf_reply_data[-1],
        conf_reply_id[-1],
        conf_reply_status[-1],
        clk, rstn,
        cBankGateSet,
        conf_config_read,
        name = name+"CPURegister_cBank")

    zPsConf = []

    for i in range(nr_of_lists):
        zPsConf.append(pass_through(conf_config_read[i], [enable[i], start_addr[i], end_addr[i], tick_nr[i], max_tick[i]], name=name+".config"+str(i)))

    zFlopEn = flop(enable, enable_d1, clk, rstn, name=name+'.fen')

    @always_comb
    def listenNew():
        for i in range(nr_of_lists):
            new_start[i].next = enable[i]==1 and enable_d1[i]==0

    # Reset tick counter to 0 for a new start, otherwise free counting
    @always_comb
    def tickCntNext():
        for i in range(nr_of_lists):
            if new_start[i] ==1:
                tick_cnt_next[i].next = 0
            else:
                if tick[tick_nr[i]]==1 and tick_cnt[i]+1 == max_tick[i]:
                    tick_cnt_next[i].next = 0
                else:
                    tick_cnt_next[i].next = tick_cnt[i] + tick[tick_nr[i]]

    @always(clk.posedge, rstn.negedge)
    def tickCnt():
        if rstn == 0:
            for i in range(nr_of_lists):
                tick_cnt[i].next = 0
        else:
            for i in range(nr_of_lists):
                tick_cnt[i].next = tick_cnt_next[i]

    @always(clk.posedge, rstn.negedge)
    def gateCnt():
        if rstn == 0:
            for i in range(nr_of_lists):
                cur_addr[i].next = 0
        else:
            for i in range(nr_of_lists):
                if new_start[i] == 1:
                    cur_addr[i].next = start_addr[i]
                else:
                    if tick[tick_nr[i]]==1 and tick_cnt[i]+1 == max_tick[i]:
                        if cur_addr[i]== end_addr[i]:
                            cur_addr[i].next = start_addr[i]
                        else:
                            cur_addr[i].next = cur_addr[i]+1


    @always_comb
    def outAddr():
        ogate_addr.next = cur_addr[igate_id]
        ogate_en.next   = enable[igate_id]


    # conf_bus_collector should be instantiated when no more append_conf_signal()
    collector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.collecotr')
        
    return instances()





def transmission_gate(
        igate_id,  # In
        ogate_on, # Out
        disabled_mask,
        request_address, request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,bus_settings,
        tick,
        clk,
        rstn,
        nr_of_lists,
        doing_init,
        gate_list_depth,
        gate_type,
        name = ''
    ):


    mem_read_latency = 1+hwconf.memory_input_flops+hwconf.memory_output_flops    
    
    if gate_type == "Ingress":
        regstr = 'ingress'
        status_w = 1
        list_index = "Ingress Gate ID"
        status_des = "ingress streams"
        status_field_name = "gateStatus"
        output_latency = mem_read_latency
    elif gate_type == "Egress":
        regstr = 'egress'
        status_w = max(hwconf.queue_max)
        list_index = "Egress Port"
        status_des = "egress queues"
        status_field_name = "disableQueueMask"
        output_latency = 0 # Egress has fixed order of selected igate_id (port number)
    else:
        print("%s ERROR! Unknown transmission gate type"%name)
        assert False
    

    nr_of_ticks  = hwconf.tick['nr_of_ticks']
    ticks_w       = (nr_of_ticks-1).bit_length()
    tick_cnt_w    = 64 # This size guarantees no wrap around in real world

    gate_list_w   = (gate_list_depth-1).bit_length()


    enable = [Signal(intbv(0)[1:0])  for  _ in range(nr_of_lists)]
    enable_d1 = [Signal(intbv(0)[1:0])  for  _ in range(nr_of_lists)]    
    start_addr = [Signal(modbv(0)[gate_list_w:0])  for _ in range(nr_of_lists)]
    tick_nr    = [Signal(modbv(0)[ticks_w:0])  for _ in range(nr_of_lists)]
    max_tick   = [Signal(modbv(0)[tick_cnt_w:0]) for _ in range(nr_of_lists)]

    new_start  = copySignal(enable)
    new_start_d1 = copySignal(enable)
    next_gate  = copySignal(enable)

    tick_cnt   = copySignal(max_tick)
    tick_cnt_next = copySignal(max_tick)

    gate_re    = Signal(intbv(0)[1:0])
    read_done  = Signal(intbv(0)[1:0])
    read_done_id = copySignal(igate_id)
    ogate_id     = copySignal(igate_id)
    gate_raddr = Signal(intbv(0, min=0, max=gate_list_depth))
    gate_odata = Signal(modbv(0)[(status_w+gate_list_w):0])
    dummy_gate_idata = copySignal(gate_odata)
    dummy_gate_we    = Signal(intbv(0)[1:0])
    dummy_gate_waddr = copySignal(gate_raddr)


    gate_omask  = Signal(modbv(0)[status_w:0])
    gate_oaddr  = Signal(modbv(0)[gate_list_w:0])


    next_addr  = [copySignal(gate_oaddr) for _ in range(nr_of_lists)]
    read_addr  = [copySignal(gate_oaddr) for _ in range(nr_of_lists)]
    read_addr_next = [copySignal(gate_oaddr) for _ in range(nr_of_lists)]

    if disabled_mask == None:
        disabled_mask = [copySignal(gate_omask)  for _ in range(nr_of_lists)]

# -- Setup CPU register: egress transmission gate


    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
    # Method for growing the lists of conf signals when a new block configuration bus is added 
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))
    

    conf_config_read = []
    cBankGateSet = conf.CTable(
        name = "regbank_%s"%(name),
        description = "",
        regtype = "reg")
    for i in range(nr_of_lists):
        cRegGateSet = conf.CRegister(
            doc_name  = "%s Transmission Gate Configuration"%gate_type,
            doc_group = "Scheduling",
            description = "Setup the start address and time intervals for the %s transmission gate. The walkthrough of the list will be restarted if the start address is changed."%regstr,
            name  = 'rg_%sGateConfig_'%regstr+str(i),
            index = list_index,
            doc_cur_id = i,
            doc_max_id = nr_of_lists,
            doc_cur_ss     = bus_settings.cur_ss,
            doc_max_ss     = bus_settings.max_ss,
            access = 'rw', # Read and write
            depth = 1)

        cRegGateSet.append(conf.CField(
            name   = "enable",
            width  = 1,
            default_value = 0,
            description = "If set, egress transmission gate is enabled for this port"))

        cRegGateSet.append(conf.CField(
            name   = "startAddr",
            width  = gate_list_w,
            description = "Start address of the transmission gate list"))

        cRegGateSet.append(conf.CField(
            name          = 'tick',
            width         = ticks_w,
            description   = 'Select one of the %d available ticks for time measurement. The tick frequencies are configured globaly in the PTP Tick Configuration register.' % (hwconf.tick['nr_of_ticks'])))

        cRegGateSet.append(conf.CField(
            name          = 'maxTick',
            width         = tick_cnt_w,
            default_value = 20,
            description   = 'Number of ticks (see Chapter \\hyperref[chap:Tick]{Tick}) between scheduled gate list.'))


        cBankGateSet.append(cRegGateSet)
        conf_config_read.append(Signal(intbv(0)[gate_list_w+1+ticks_w+tick_cnt_w:0]))
        
    bus_settings.append(cBankGateSet)
    append_conf_signal() # Grow the conf reply lists to accomodate the disable_queue_output regbank
    iGateSet = register(
        request_address,
        request_data,
        request_id,
        request_type,
        request_re,
        request_we,
        conf_reply_data[-1],
        conf_reply_id[-1],
        conf_reply_status[-1],
        clk, rstn,
        cBankGateSet,
        conf_config_read,
        name = name+"CPURegister_cBank")




    cBankCList = conf.CTable(
        doc_name = "%s Transmission Gate List"%gate_type,
        name = "r_list"+name,
        doc_group = "Scheduling",        
        doc_cur_ss     = bus_settings.cur_ss,
        doc_max_ss     = bus_settings.max_ss,
        description = "Gate control list for %s. Each entry gives ON or OFF status of %s for the current time window, as well as a flag to either jump to the next entry or back to the start address for the next time window."%(status_des, status_des),
        regtype = "mem")

    cRegCList = conf.CRegister(
        name  = "reg",
        index = "Transmission Gate Address",
        depth     = gate_list_depth)

    cRegCList.append(conf.CField(
        name  = status_field_name,  
        width = status_w,
        description = "Each bit refers to a gate status. \\tabTwo{Packet transmission is allowed.}{Packet transmission is not allowed.}"))
    cRegCList.append(conf.CField(
        name  = "nextAddr",
        width = gate_list_w,
        default_value = 0,
        description = "Determine which transmission gate to use when the current period is ended."))

    cBankCList.append(cRegCList)
    bus_settings.append(cBankCList)

    append_conf_signal() # Grow the reply list    
    iGateList = mem_cpu_if(
        request_address = request_address, 
        request_data    = request_data,  
        request_id      = request_id,     
        request_type    = request_type,   
        request_re      = request_re,     
        request_we      = request_we,     
        reply_data      = conf_reply_data[-1],     
        reply_id        = conf_reply_id[-1],       
        reply_status    = conf_reply_status[-1],   
        doing_init      = doing_init,
        clk             = clk,            
        rstn            = rstn,           
        settings        = cBankCList,       
        hw_idata        = dummy_gate_idata,
        hw_odata        = gate_odata,       
        hw_raddr        = gate_raddr,
        hw_waddr        = dummy_gate_waddr,       
        hw_re           = gate_re,
        hw_we           = dummy_gate_we,
        input_flops     = hwconf.memory_input_flops,
        output_flops    = hwconf.memory_output_flops,
        name=name+'.gateList')

    logic_zero = Signal(intbv(0)[1:0])
    zPsDummy = pass_through(logic_zero, dummy_gate_we, name=name+".we0")

    zPsConf = []

    for i in range(nr_of_lists):
        zPsConf.append(pass_through(conf_config_read[i], [enable[i], start_addr[i], tick_nr[i], max_tick[i]], name=name+".config"+str(i)))

    zFlopEn = flop(enable, enable_d1, clk, rstn, name=name+'.fen')


    @always_comb
    def listenNew():
        for i in range(nr_of_lists):
            new_start[i].next = enable[i]==1 and enable_d1[i]==0
    zFlopNstart = flop(new_start, new_start_d1, clk, rstn, name=name+'.start')

    # Reset tick counter to 0 for a new start, otherwise free counting
    @always_comb
    def tickCntNext():
        for i in range(nr_of_lists):
            if new_start[i] ==1:
                tick_cnt_next[i].next  = 0
                next_gate[i].next = 0
            else:
                if tick[tick_nr[i]]==1 and tick_cnt[i]+1 >= max_tick[i]:
                    tick_cnt_next[i].next = 0
                    next_gate[i].next = 1
                else:
                    tick_cnt_next[i].next = tick_cnt[i] + tick[tick_nr[i]]
                    next_gate[i].next = 0

    zMultRen  = multiflop(gate_re, read_done, clk, rstn, depth=mem_read_latency, name=name+'.pipeRen')
    zMultPort = multiflop(igate_id, read_done_id, clk, rstn, depth=mem_read_latency, name=name+'.pipeRport')
    zPsRdata = pass_through(gate_odata, [gate_omask, gate_oaddr], name=name+'.godata')

    zOutPort = multiflop(igate_id, ogate_id, clk, rstn, depth=output_latency, name=name+'.oId')

    @always_comb
    def getRd():
        if enable[igate_id]==1:
            gate_re.next = 1
            gate_raddr.next = read_addr[igate_id]
        else:
            gate_re.next = 0
            gate_raddr.next = 0
            

    
    # Update the pointer to the next gate
    @always(clk.posedge, rstn.negedge)
    def nextAddr():
        if rstn == 0:
            for i in range(nr_of_lists):
                next_addr[i].next = 0
                disabled_mask[i].next = 0
        else:
            if read_done:
                next_addr[read_done_id].next = gate_oaddr
                disabled_mask[read_done_id].next = gate_omask
    
    # 
    @always_comb
    def addrNext():
        for i in range(nr_of_lists):
            if new_start[i] == 1:
                read_addr_next[i].next = start_addr[i]
            else:
                if next_gate[i] == 1 and enable[i]==1:
                    read_addr_next[i].next = next_addr[i]
                else:
                    read_addr_next[i].next = read_addr[i]


    @always(clk.posedge, rstn.negedge)
    def tickReg():
        if rstn == 0:
            for i in range(nr_of_lists):
                tick_cnt[i].next = 0
                read_addr[i].next = 0
        else:
            for i in range(nr_of_lists):
                tick_cnt[i].next = tick_cnt_next[i]
                read_addr[i].next = read_addr_next[i]



    @always_comb
    def driveOut():
        ogate_on.next = ~ disabled_mask[ogate_id]
        


    # conf_bus_collector should be instantiated when no more append_conf_signal()
    collector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.collecotr')

    return instances()
    

