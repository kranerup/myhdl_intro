import sys
from myhdl import *
from modules.common.Common import copySignal, pass_through, multiflop
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
from .mmd_algo import mmd_algo
from .mmd_conf_wrap import mmd_conf_wrap

"""
One MMD used by all swich slices
"""
def mmd_bank(
        read_info, # list of slices
        pkt_bytes,
        icolor,
        idrop,
        ocolor,
        odrop,
        clk,
        rstn,
        # Configuration interface
        request_address,
        request_data,
        request_id,
        request_type,
        request_re,
        request_we,
        reply_data,
        reply_id,
        reply_status,
        tick,
        doing_init,
        bus_settings,
        depth,
        desc_w,
        desc_d,
        desc_name,
        doc_group,
        algo_latency,
        ropt_latency,
        input_latency,
        name):
    

    nr_of_slices = len(read_info)

    parallel_buckets = 2
    token_w  = 12
    bucket_w = 16
    ifg_w    = 8
    
    MMD_LATENCY = 1+hwconf.memory_input_flops+hwconf.memory_output_flops
    MMD_LATENCY += ropt_latency

    conf_read_valid  = [Signal(intbv(0)[1:0]) for _ in range(nr_of_slices)]
    conf_read_addr   = [Signal(intbv(0, min=0, max=depth))  for _ in range(nr_of_slices)]

    conf_ocap_1 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    conf_ocap_2 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    
    conf_otoken_1 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    conf_otoken_2 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    conf_itoken_1 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    conf_itoken_2 =  [Signal(modbv(0)[bucket_w:0]) for _ in range(nr_of_slices)]
    conf_mmd_mode     =  [Signal(intbv(0)[2:0]) for _ in range(nr_of_slices)]
    conf_drop_mode    =  [Signal(intbv(0)[3:0]) for _ in range(nr_of_slices)]
    conf_adj_token    =  [Signal(modbv(0)[ifg_w:0]) for _ in range(nr_of_slices)]
    conf_adj_mode     =  [Signal(modbv(0)[1:0]) for _ in range(nr_of_slices)]    

    conf_osply_token_1  = [Signal(intbv(0, min=0, max=2**bucket_w*2)) for _ in range(nr_of_slices)]
    conf_osply_token_2  = [Signal(intbv(0, min=0, max=2**bucket_w)) for _ in range(nr_of_slices)]
    conf_oentry_reset   = [Signal(intbv(0)[1:0]) for _ in range(nr_of_slices)]
    
    conf_write_valid = copySignal(conf_read_valid)
    conf_write_addr  = copySignal(conf_read_addr)


    # Input pipeline
    read_info_x = copySignal(read_info)
    read_info_filt = copySignal(read_info)    
    pkt_bytes_x = copySignal(pkt_bytes)

    zPipeInfo  = multiflop(read_info, read_info_x, clk, rstn, depth=input_latency, name=name+".pipeInfo")
    zPipeBytes = multiflop(pkt_bytes, pkt_bytes_x, clk, rstn, depth=input_latency, name=name+".pipeBytes")

    icolor_list = [Signal(intbv(0)[2:0])  for _ in range(nr_of_slices)]
    idrop_list = [Signal(intbv(0)[1:0])  for _ in range(nr_of_slices)]    

    zPsColor = pass_through(icolor, icolor_list, name=name+".ic")
    zPsDrop  = pass_through(idrop, idrop_list, name=name+".id")    
    

    @always_comb
    def infoFilt():
        for i in range(nr_of_slices):
            if idrop[i] == 1:
                read_info_filt[i].next = 0
            else:
                read_info_filt[i].next = read_info_x[i]

    iProc = []
    for i in range(nr_of_slices):
        iProc.append(mmd_algo(
            read_info  = read_info_filt[i],
            pkt_bytes  = pkt_bytes_x[i],
            icolor     = icolor_list[i],
            idrop      = idrop_list[i],
            ocolor     = ocolor,
            odrop      = odrop,
            # interface to conf mem
            conf_read_valid  =  conf_read_valid[i],
            conf_read_addr   =  conf_read_addr[i],
            conf_otoken_1         = conf_otoken_1[i],
            conf_otoken_2         = conf_otoken_2[i],
            conf_osply_token_1    = conf_osply_token_1[i],
            conf_osply_token_2    = conf_osply_token_2[i],
            conf_ocap_1           = conf_ocap_1[i],
            conf_ocap_2           = conf_ocap_2[i],
            conf_oentry_reset     = conf_oentry_reset[i],
            conf_mmd_mode         = conf_mmd_mode[i],
            conf_drop_mode        = conf_drop_mode[i],
            conf_adj_token        = conf_adj_token[i],
            conf_adj_mode         = conf_adj_mode[i],
            conf_write_valid      = conf_write_valid[i],
            conf_write_addr       = conf_write_addr[i],
            conf_itoken_1         = conf_itoken_1[i],
            conf_itoken_2         = conf_itoken_2[i],
            # 
            clk        = clk,
            rstn       = rstn,
            bucket_w         = bucket_w,
            algo_latency     = algo_latency,
            MMD_LATENCY      = MMD_LATENCY,
            name       = name+'.mmdAlgo'+str(i)))


    # Shared conf mem
    iMmdConf = mmd_conf_wrap(
        read_valid            = conf_read_valid, # list
        read_addr             = conf_read_addr,  # list 

        otoken_1              = conf_otoken_1,
        otoken_2              = conf_otoken_2,
        osply_token_1         = conf_osply_token_1,
        osply_token_2         = conf_osply_token_2,
        ocap_1                = conf_ocap_1,
        ocap_2                = conf_ocap_2,
        oentry_reset          = conf_oentry_reset,
        ommd_mode             = conf_mmd_mode,
        odrop_mode            = conf_drop_mode,
        oadj_mode             = conf_adj_mode,        
        oadj_token            = conf_adj_token,
        
        write_valid           = conf_write_valid,
        write_addr            = conf_write_addr,

        itoken_1              = conf_itoken_1,
        itoken_2              = conf_itoken_2,

        tick                  = tick,
        doing_init            = doing_init,
        clk                   = clk,
        rstn                  = rstn,
        # Configuration interface
        request_address  = request_address,
        request_data     = request_data,
        request_id       = request_id,
        request_type     = request_type,
        request_re       = request_re,
        request_we       = request_we,
        reply_data       = reply_data,
        reply_id         = reply_id,
        reply_status     = reply_status,
        bus_settings     = bus_settings,
        parallel_buckets = parallel_buckets,
        token_w     = token_w,
        bucket_w    = bucket_w,
        ifg_w       = ifg_w,
        depth       = depth,
        desc_w      = desc_w,
        desc_d      = desc_d,
        desc_name   = desc_name,
        doc_group   = doc_group,
        algo_latency = algo_latency,
        setup_latency = ropt_latency,
        name        = name+".conf")

    
    return instances()
