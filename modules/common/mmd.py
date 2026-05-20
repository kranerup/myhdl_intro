import sys
from myhdl import *
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.common.Common import copySignal, pass_through, listType, flop, OR, multiflop
from modules.common.Common import hwdir
from modules.conf import conf
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
from modules.conf.register_table import register_table
from .mmd_bank import mmd_bank

"""
Ingress/egress meter-marker-dropper
N MMDs x M slices
"""
def mmd(
        immd_ptr,       # List, flattened pointer
        icolor,
        ivalid_bytes,
        ifirst,
        ilast,
        iport,
        
        olast_color,
        olast_drop,
        clk,rstn,

        # Configuration interface
        request_address,request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,
        tick,
        doing_init,
        pac_defs,
        i2e_bytes,
        bus_settings = [],
        algo_latency = 1,
        ropt_latency = 1,
        one_bank_latency = 1,
        desc_name    = [],
        mmd_depth    = [],
        name = ''):


    nr_of_mmd = len(desc_name)

    nr_of_ports  = hwconf.nr_of_ports

    cnt_width = hwconf.statistics_config['conf_width']
    conf_access = hwconf.statistics_config['conf_access']

    nr_of_slices = len(immd_ptr)
    
    color_width = 2
    bytes_w = 32 # TODO

    zPs = []

    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
    conf_doing_init     = []

    # Method for growing the lists of conf signals when a new block configuration bus is added 
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))


    conf_width = hwconf.statistics_config['conf_width']
    conf_access = hwconf.statistics_config['conf_access']        

    # Drop statistics
    cBankDrop = conf.CTable(
                            name           = 'count_drop_'+name,
                            description    = 'Registers for counting dropped packets in the ingress/egress admission control',
                            regtype        = 'reg')
    cFieldDrop  = conf.CField(
                            name           = 'packets',
                            width          = conf_width,
                            description    = 'Number of dropped packets.')
    cRegDrop = conf.CRegister(
                            doc_name       = 'Ingress/Egress Admission Control Drop',
                            doc_group      = 'Statistics',
                            description    = 'Number of packets dropped due to ingress/egress admission control. \\mmp',
                            name           = 'rg_count_drop',
                            attributes     = ['drop_counter_check', {'block':'ipp_mmp','name':'mmp','type':'drop'}],
                            index          = '',
                            access         = conf_access,
                            depth          = 1)
    cRegDrop.append(cFieldDrop)
    cBankDrop.append(cRegDrop)
    bus_settings.append(cBankDrop)


    logic_high = Signal(intbv(1)[1:0])
    
    drop_cnt     = [ Signal(intbv(0)[cnt_width:0]) ]
    drop_cnt_we  = [ Signal(intbv(0)[1:0])]
    drop_cnt_next = copySignal(drop_cnt)
    
    zDropWe = pass_through(logic_high, drop_cnt_we[0], name=name+".we")

    @always_comb
    def dropNext():
        tmp_drop = intbv(0, min=0, max=nr_of_slices+1)
        for i in range(nr_of_slices):
            tmp_drop[:] = tmp_drop + olast_drop[i]
        drop_cnt_next[0].next = drop_cnt[0] + tmp_drop
    
    
    append_conf_signal()
    iDrop = register_table(
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
        settings        = cBankDrop,
        register_read   = drop_cnt,
        register_we     = drop_cnt_we,
        register_write  = drop_cnt_next,
        name            = name +'CPURegister_drop_counter')

    
    
    bytes_cnt = [ Signal(intbv(0)[bytes_w:0])  for _ in range(nr_of_ports)] # TODO

    tail_valid  = [Signal(intbv(0)[1:0])  for _ in range(nr_of_slices)]
    tail_port   = copySignal(iport)


#    ptr_valid_reg = [Signal(intbv(0)[nr_of_mmd:0])  for _ in range(nr_of_ports)]
#    ptr_reg       = [Signal(intbv(0)[nr_of_mmd*ptr_width:0]) for _ in range(nr_of_ports)]
    ptr_reg       = [copySignal(immd_ptr[0]) for _ in range(nr_of_ports)]
    color_reg     = [Signal(intbv(0)[2:0])  for _ in range(nr_of_ports)]
     

    @always(clk.posedge, rstn.negedge)
    def byteCnt():
        if rstn == 0:
            for i in range(nr_of_slices):
                tail_valid[i].next = 0
                tail_port[i].next = 0
            for i in range(nr_of_ports):
                bytes_cnt[i].next = 0
                ptr_reg[i].next = 0
                color_reg[i].next = 0
        else:
            for i in range(nr_of_slices):
                if ilast[i] == 1 and ivalid_bytes[i] > 0:
                    tail_valid[i].next = 1
                    tail_port[i].next = iport[i]
                else:
                    tail_valid[i].next = 0
                    tail_port[i].next = 0

                if ifirst[i] == 1:
                    bytes_cnt[iport[i]].next = ivalid_bytes[i]-i2e_bytes
                    ptr_reg[iport[i]].next = immd_ptr[i]
                    color_reg[iport[i]].next = icolor[i]
                elif ivalid_bytes[i] > 0:
                    bytes_cnt[iport[i]].next = bytes_cnt[iport[i]]+ivalid_bytes[i]

                    
    ptr_flat       = copySignal(immd_ptr)
    pkt_color      = [Signal(intbv(0)[2:0])  for _ in range(nr_of_slices)]
    pkt_bytes      = [Signal(intbv(0)[bytes_w:0]) for _ in range(nr_of_slices)]


    @always_comb
    def toMmd():
        for i in range(nr_of_slices):
            if tail_valid[i] == 1:
                ptr_flat[i].next  = ptr_reg[tail_port[i]]
                pkt_color[i].next = color_reg[tail_port[i]]
                pkt_bytes[i].next  = bytes_cnt[tail_port[i]]
            else:
                ptr_flat[i].next = 0
                pkt_color[i].next = 0
                pkt_bytes[i].next  = 0


    # (nr_of_mmd x nr_of_slices) to (nr_of_slices x nr_of_mmd)
    ptr_list =  [ [Signal(intbv(0)[((depth-1).bit_length()+1):0])  for depth in mmd_depth ]
                  for _ in range(nr_of_slices)]
    for i in range(nr_of_slices):
        zPs.append( pass_through(ptr_flat[i], ptr_list[i], name=name+".ptrl"))
    

    ptr_trans = [ [] for _ in range(nr_of_mmd) ]
    for i in range(nr_of_slices):
        for j in range(nr_of_mmd):
            ptr_trans[j].append(ptr_list[i][j])


    # Each mmd handles request from all slices

    
    # Parallel MMD bank
    """
    mmd_color = [Signal(intbv(0)[color_width*nr_of_slices:0]) for _ in range(nr_of_mmd)]
    mmd_drop  = [Signal(intbv(0)[nr_of_slices:0])   for _ in range(nr_of_mmd)]

    iBank = []
    for i in range(nr_of_mmd):
    
        append_conf_signal() # Grow the conf reply bus
        conf_doing_init.append(Signal(intbv(0)[1:0]))        
        iBank.append(mmd_bank(
            read_info  = ptr_trans[i],
            pkt_bytes  = pkt_bytes, # shared by all mmd
            icolor     = pkt_color,

            ocolor     = mmd_color[i],
            odrop      = mmd_drop[i],
            clk        = clk,
            rstn       = rstn,
            # Configuration interface
            request_address  = request_address,
            request_data     = request_data,
            request_id       = request_id,
            request_type     = request_type,
            request_re       = request_re,
            request_we       = request_we,
            reply_data       = conf_reply_data[-1],
            reply_id         = conf_reply_id[-1],
            reply_status     = conf_reply_status[-1],
            tick             = tick,
            doing_init       = conf_doing_init[i],
            bus_settings     = bus_settings,
            depth            = mmd_depth[i],
            desc_w           = "Egress Ports",
            desc_d           = "Meter Pointer",
            desc_name        = desc_name[i],
            doc_group        = "Admission Control",
            algo_latency     = algo_latency,
            name       = name+'.mmd'+str(i)))

        

    # Should match the conf settings
    GREEN  = 0
    YELLOW = 1
    RED    = 2


    # If there is more than one mmd, select color from the worst one
    @always(clk.posedge,rstn.negedge)
    def colorSel():
        if rstn == 0:
            for i in range(nr_of_slices):
                olast_color[i].next = 0
                olast_drop[i].next = 0
        else:
            ref_color = modbv(GREEN)[2:0]
            tmp_color = modbv(GREEN)[2:0]
            tmp_drop  = modbv(0)[1:0]
            for i in range(nr_of_slices):
                tmp_color[:] = GREEN
                tmp_drop[:] = 0
                for j in range(nr_of_mmd):
                    ref_color[:] = mmd_color[j] >> (2*i)
                    if ref_color > tmp_color:
                        tmp_color[:] = ref_color
                    tmp_drop[:] = tmp_drop | (mmd_drop[j] >> i)

                olast_color[i].next = tmp_color
                olast_drop[i].next = tmp_drop

    """

    # Serail MMD bank

    
    mmd_icolor = [Signal(intbv(0)[color_width*nr_of_slices:0]) for _ in range(nr_of_mmd)]
    mmd_ocolor = [Signal(intbv(0)[color_width*nr_of_slices:0]) for _ in range(nr_of_mmd)]

    mmd_idrop  = [Signal(intbv(0)[nr_of_slices:0])   for _ in range(nr_of_mmd)]
    mmd_odrop  = [Signal(intbv(0)[nr_of_slices:0])   for _ in range(nr_of_mmd)]


    tie_low = Signal(intbv(0)[nr_of_slices:0])
    zPsSerial = []
    for i in range(nr_of_mmd):
        if i == 0:
            zPsSerial.append(pass_through(pkt_color, mmd_icolor[i], name=name+".pcol"))
            zPsSerial.append(pass_through(tie_low, mmd_idrop[i], name=name+".mdrop"))            
        else:
            zPsSerial.append(flop(mmd_ocolor[i-1], mmd_icolor[i], clk, rstn))
            zPsSerial.append(flop(mmd_odrop[i-1], mmd_idrop[i], clk, rstn))
        if i==nr_of_mmd-1: # last one
            zPsSerial.append(flop(mmd_ocolor[i], olast_color, clk, rstn))
            zPsSerial.append(flop(mmd_odrop[i], olast_drop, clk, rstn))
    
    iBank = []
    input_latency = 0
    for i in range(nr_of_mmd):
        append_conf_signal() # Grow the conf reply bus
        conf_doing_init.append(Signal(intbv(0)[1:0]))        
        iBank.append(mmd_bank(
            read_info  = ptr_trans[i],
            pkt_bytes  = pkt_bytes, # shared by all mmd
            icolor     = mmd_icolor[i],
            idrop      = mmd_idrop[i],

            ocolor     = mmd_ocolor[i],
            odrop      = mmd_odrop[i],
            clk        = clk,
            rstn       = rstn,
            # Configuration interface
            request_address  = request_address,
            request_data     = request_data,
            request_id       = request_id,
            request_type     = request_type,
            request_re       = request_re,
            request_we       = request_we,
            reply_data       = conf_reply_data[-1],
            reply_id         = conf_reply_id[-1],
            reply_status     = conf_reply_status[-1],
            tick             = tick,
            doing_init       = conf_doing_init[i],
            bus_settings     = bus_settings,
            depth            = mmd_depth[i],
            desc_w           = "Egress Ports",
            desc_d           = "Meter Pointer",
            desc_name        = desc_name[i],
            doc_group        = "Admission Control",
            algo_latency     = algo_latency,
            ropt_latency     = ropt_latency,
            input_latency    = input_latency,
            name       = name+'.mmd'+str(i)))

        # Update input latency
        input_latency += one_bank_latency


    # conf_bus_collector should be instantiated when no more append_conf_signal()
    iCollector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.collecotr')

    zOrinit = OR(conf_doing_init, None, doing_init, name=name+"conforinit")

    return instances()
    
