from myhdl import *
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.conf.mem_cpu_if import mem_cpu_if
from modules.common.Common import copySignal, pass_through, listType, flop, OR, pipeline
from modules.common.memory import memory_init
from .mmd_mem_conf import mmd_mem_conf

import sys
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


def mmd_conf_wrap(
        read_valid,
        read_addr,

        otoken_1,
        otoken_2,
        osply_token_1,
        osply_token_2,
        ocap_1,
        ocap_2,
        oentry_reset,
        ommd_mode,
        odrop_mode,
        oadj_mode,
        oadj_token,
        
        write_valid,
        write_addr,

        itoken_1,
        itoken_2,

        tick,
        doing_init,
        clk,
        rstn,
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
        parallel_buckets,
        token_w,
        bucket_w,
        ifg_w,
        depth,
        desc_w,
        desc_d,
        desc_name,
        doc_group,
        algo_latency,
        setup_latency,
        name):

    nr_of_slices = len(read_valid)


    # Decode configurations
    if parallel_buckets != 2:
        print("%s: ERROR! MMD only supports 2 parallel buckets"%name)
        assert False
    nr_of_ticks   = len(tick)
    ticks_w       = (nr_of_ticks-1).bit_length()
    
    tcnt_w          = 32 # TODO: calculate it

    config_w = (bucket_w+token_w+ticks_w)*parallel_buckets+1+1+3+ifg_w+1
    

    tick_cnt    = [Signal(modbv(0)[tcnt_w:0])  for _ in range(nr_of_ticks)]

        

    conf_otokens = [Signal(intbv(0)[bucket_w*2:0])  for _ in range(nr_of_slices)]
    conf_oconfig = [Signal(intbv(0)[config_w:0])  for _ in range(nr_of_slices)]
    conf_oreset  = [Signal(intbv(0)[1:0])  for _ in range(nr_of_slices)]
    
    conf_itokens = [Signal(intbv(0)[bucket_w*2:0])  for _ in range(nr_of_slices)]
    
    shadow_itimestamp   = [Signal(intbv(0)[tcnt_w*2:0])  for _ in range(nr_of_slices)]
    shadow_otimestamp   = [Signal(intbv(0)[tcnt_w*2:0])  for _ in range(nr_of_slices)]

    token_read_enable = [Signal(intbv(0)[1:0])  for _ in range(nr_of_slices)]
    setup_read_enable = [Signal(intbv(0)[1:0])  for _ in range(nr_of_slices)]    

    shadow_write_enable = [Signal(intbv(0)[1:0]) for _ in range(nr_of_slices)]
    shadow_write_addr   = copySignal(read_addr)
    
    
    # Tick counter
    @always(clk.posedge, rstn.negedge)
    def tickCnt():
        if rstn == 0:
            for i in range(nr_of_ticks):
                tick_cnt[i].next = 0
        else:
            for i in range(nr_of_ticks):
                tick_cnt[i].next = tick_cnt[i]+tick[i]

    
    
    # TODO: multi read mem for multi slice designs

    if nr_of_slices == 1:
        iMem = mmd_mem_conf(
            read_addr           = read_addr[0],
            read_valid          = read_valid[0],

            token_read_enable   = token_read_enable[0],
            setup_read_enable   = setup_read_enable[0],

            timestamp_write_enable = shadow_write_enable[0],
            timestamp_write_addr   = shadow_write_addr[0],
            itimestamp     = shadow_itimestamp[0],

            conf_otokens      = conf_otokens[0],
            conf_oconfig      = conf_oconfig[0],
            conf_oreset       = conf_oreset[0],
            otimestamp        = shadow_otimestamp[0],

            token_write_valid    = write_valid[0],
            token_write_addr     = write_addr[0],
            conf_itokens   = conf_itokens[0],
            doing_init     = doing_init,
            clk                 = clk,
            rstn                = rstn,

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
            ticks_w     = ticks_w,
            depth       = depth,
            desc_w      = desc_w,
            desc_d      = desc_d,
            desc_name   = desc_name,
            doc_group   = doc_group,
            conf_type   = "mem",
            algo_latency = algo_latency,
            name        = name+".confmem")
    else:
        print("ERROR! Not supported yet!")
        assert False




    iPost = []
    for i in range(nr_of_slices):
        iPost.append(mmd_conf_decode(
            tick_cnt            = tick_cnt,
            read_valid          = read_valid[i],
            read_addr           = read_addr[i],
            token_read_enable   = token_read_enable[i],
            setup_read_enable   = setup_read_enable[i],
            conf_otokens        = conf_otokens[i],
            conf_oconfig        = conf_oconfig[i],
            conf_oreset         = conf_oreset[i],
            conf_itokens        = conf_itokens[i],

            shadow_write_enable = shadow_write_enable[i],
            shadow_write_addr   = shadow_write_addr[i],
            shadow_itimestamp   = shadow_itimestamp[i],
            shadow_otimestamp   = shadow_otimestamp[i],

            otoken_1            = otoken_1[i],
            otoken_2            = otoken_2[i],
            osply_token_1       = osply_token_1[i],
            osply_token_2       = osply_token_2[i],
            ocap_1              = ocap_1[i],
            ocap_2              = ocap_2[i],
            oentry_reset        = oentry_reset[i],
            ommd_mode           = ommd_mode[i],
            odrop_mode          = odrop_mode[i],
            oadj_mode           = oadj_mode[i],
            oadj_token          = oadj_token[i],
        
            itoken_1            = itoken_1[i],
            itoken_2            = itoken_2[i],

            clk                 = clk,
            rstn                = rstn,
            ticks_w             = ticks_w,
            token_w             = token_w,
            bucket_w            = bucket_w,
            ifg_w               = ifg_w,
            tcnt_w              = tcnt_w,
            config_w            = config_w,
            algo_latency        = algo_latency,
            setup_latency       = setup_latency,
            name                = name+'.confDecode'+str(i)))

    return instances()


def mmd_conf_decode(
        tick_cnt,
        read_valid,
        read_addr,
        token_read_enable,
        setup_read_enable,
        conf_otokens,
        conf_oconfig,
        conf_oreset,
        conf_itokens,

        shadow_write_enable,
        shadow_write_addr,
        shadow_itimestamp,
        shadow_otimestamp,
        
        otoken_1,
        otoken_2,
        osply_token_1,
        osply_token_2,
        ocap_1,
        ocap_2,
        oentry_reset,
        ommd_mode,
        odrop_mode,
        oadj_mode,
        oadj_token,
        itoken_1,
        itoken_2,
        clk,
        rstn,
        ticks_w,
        token_w,
        bucket_w,
        ifg_w,
        tcnt_w,
        config_w,
        algo_latency,
        setup_latency,
        name):
    

    MAX_TICK_CNT = 2**tcnt_w
    MAX_CAP_2 = 2**bucket_w-1
    MAX_CAP_1 = MAX_CAP_2*2
    

    
    # Split to two token buckets        
    cap_1 = Signal(modbv(0)[bucket_w:0])
    cap_2 = Signal(modbv(0)[bucket_w:0])
    add_token_1 = Signal(modbv(0)[token_w:0])
    add_token_2 = Signal(modbv(0)[token_w:0])
    tick_idx_1  = Signal(modbv(0)[ticks_w:0])
    tick_idx_2  = Signal(modbv(0)[ticks_w:0])

    token_1 = Signal(modbv(0)[bucket_w:0])
    token_2 = Signal(modbv(0)[bucket_w:0])

    mmd_mode     = Signal(intbv(0)[2:0])
    adj_mode     = Signal(intbv(0)[1:0])
    adj_token    = Signal(modbv(0)[ifg_w:0])
    drop_mode    = Signal(intbv(0)[3:0])
    entry_reset = Signal(intbv(0)[1:0])

    ts_1    = Signal(modbv(0)[tcnt_w:0])
    ts_2    = Signal(modbv(0)[tcnt_w:0])    

    new_ts_1 = Signal(modbv(0)[tcnt_w:0])
    new_ts_2 = Signal(modbv(0)[tcnt_w:0])
    last_ts_1 = Signal(modbv(0)[tcnt_w:0])
    last_ts_2 = Signal(modbv(0)[tcnt_w:0])
    
    new_ts_1_d1 = Signal(modbv(0)[tcnt_w:0])
    new_ts_2_d1 = Signal(modbv(0)[tcnt_w:0])

    
    delta_ts_1 = Signal(modbv(0)[tcnt_w:0])
    delta_ts_2 = Signal(modbv(0)[tcnt_w:0])
    

    zPip = []
    mmd_mode_d      = [copySignal(mmd_mode)     for _ in range(setup_latency+1)]
    drop_mode_d     = [copySignal(drop_mode)    for _ in range(setup_latency+1)]
    adj_token_d     = [copySignal(adj_token)    for _ in range(setup_latency+1)]
    adj_mode_d      = [copySignal(adj_mode)     for _ in range(setup_latency+1)]
    
    token_1_d       = [copySignal(token_1)  for _ in range(setup_latency+1)]
    token_2_d       = [copySignal(token_2)  for _ in range(setup_latency+1)]
    cap_1_d         = [copySignal(cap_1)  for _ in range(setup_latency+1)]
    cap_2_d         = [copySignal(cap_2)  for _ in range(setup_latency+1)]
    entry_reset_d   = [copySignal(entry_reset)  for _ in range(setup_latency+1)]

    zPip.append( pipeline( token_1,   token_1_d,   clk, rstn))
    zPip.append( pipeline( token_2,   token_2_d,   clk, rstn))    
    zPip.append( pipeline( cap_1,     cap_1_d,   clk, rstn))
    zPip.append( pipeline( cap_2,     cap_2_d,   clk, rstn))
    zPip.append( pipeline( entry_reset,     entry_reset_d,   clk, rstn))
    zPip.append( pipeline( adj_token,     adj_token_d,   clk, rstn))
    zPip.append( pipeline( adj_mode,     adj_mode_d,   clk, rstn))    
    zPip.append( pipeline( mmd_mode,     mmd_mode_d,   clk, rstn))
    zPip.append( pipeline( drop_mode,    drop_mode_d,   clk, rstn))    
    
    @always(clk.posedge, rstn.negedge)
    def tsWrite():
        if rstn == 0:
            new_ts_1_d1.next = 0
            new_ts_2_d1.next = 0            
        else:
            new_ts_1_d1.next = new_ts_1
            new_ts_2_d1.next = new_ts_2
                

                
    zPsConfig = pass_through(conf_oconfig, [cap_1, add_token_1, tick_idx_1, cap_2, add_token_2,
                                           tick_idx_2, mmd_mode, drop_mode, adj_mode, adj_token], name=name+".oconf")


    @always_comb
    def splitPara():
        token_1.next = conf_otokens
        token_2.next = conf_otokens >> bucket_w
        entry_reset.next = conf_oreset
        ts_1.next    = shadow_otimestamp
        ts_2.next    = shadow_otimestamp >> tcnt_w


    @always_comb
    def newTs():
        new_ts_1.next = tick_cnt[tick_idx_1]
        new_ts_2.next = tick_cnt[tick_idx_2]


    # MEM Read pipes
    read_latency = 1 + hwconf.memory_input_flops + hwconf.memory_output_flops
    read_latency += setup_latency
    pipe_depth   = read_latency+algo_latency # To algo
    pipe_tot     = pipe_depth+1
    forward = Signal(intbv(0, min=0, max=pipe_tot))
    forward_d = [ copySignal(forward) for _ in range(read_latency+1) ]

    read_valid_d = [copySignal(read_valid)      for _ in range(pipe_tot)]
    read_addr_d  = [copySignal(read_addr)       for _ in range(pipe_tot)]
    itoken_1_d   = [copySignal(itoken_1)       for _ in range(pipe_tot)]
    itoken_2_d   = [copySignal(itoken_2)       for _ in range(pipe_tot)]
    
    zPip.append(pipeline(read_valid, read_valid_d, clk, rstn, name=name+'.zPipValid'))
    zPip.append(pipeline(read_addr, read_addr_d, clk, rstn, name=name+'.zPipAddr'))
    zPip.append(pipeline(itoken_1, itoken_1_d, clk, rstn, name=name+'.zPipToken1'))
    zPip.append(pipeline(itoken_2, itoken_2_d, clk, rstn, name=name+'.zPipToken1'))

    zPip.append(pipeline(forward, forward_d, clk, rstn, name=name+'zPipforward'))
    

    @always_comb
    def countforw():
        tforward = intbv(0, min=0, max=pipe_tot)
        tforward[:] = 0
        if read_valid == 1: # New read, check un-written addresses
            for p in range(1, pipe_tot):
                if tforward==0 and read_valid_d[p]==1 and read_addr_d[p]==read_addr_d[0]:
                    tforward[:] = p
        forward.next = tforward


    @always_comb
    def memRdata():
        ommd_mode.next  = mmd_mode_d[setup_latency]
        oadj_mode.next  = adj_mode_d[setup_latency]
        oadj_token.next = adj_token_d[setup_latency]
        odrop_mode.next = drop_mode_d[setup_latency]
        ocap_1.next = cap_1_d[setup_latency]
        ocap_2.next = cap_2_d[setup_latency]
        if forward_d[read_latency] > 0:
            otoken_1.next = itoken_1_d[forward_d[read_latency]-algo_latency]
            otoken_2.next = itoken_2_d[forward_d[read_latency]-algo_latency]
            oentry_reset.next = 0 # reset from conf bus is blocked under forward read
        else:
            otoken_1.next = token_1_d[setup_latency]
            otoken_2.next = token_2_d[setup_latency]
            oentry_reset.next = entry_reset_d[setup_latency]

            
    # Timestamp pipelines
    ts_latency    = 1 + hwconf.memory_input_flops + hwconf.memory_output_flops
    pipe_ts_tot = ts_latency+1
    ts_forward  = Signal(intbv(0, min=0, max=pipe_ts_tot))
    ts_forward_d = [copySignal(ts_forward)  for _ in range(pipe_ts_tot)]

    write_ts_1_d = [copySignal(last_ts_1)  for _ in range(pipe_ts_tot)]
    write_ts_2_d = [copySignal(last_ts_2)  for _ in range(pipe_ts_tot)]
    
    
    zPip.append(pipeline(ts_forward, ts_forward_d, clk, rstn, name=name+'zPiptsfwd'))
    zPip.append(pipeline(new_ts_1_d1, write_ts_1_d, clk, rstn, name=name+'zPipts1fwd'))
    zPip.append(pipeline(new_ts_2_d1, write_ts_2_d, clk, rstn, name=name+'zPipts2fwd'))        
    
    @always_comb
    def counttsforw():
        tforward = intbv(0, min=0, max=pipe_tot)
        tforward[:] = 0
        if read_valid == 1: # New read, check un-written addresses
            for p in range(1, pipe_ts_tot):
                if tforward==0 and read_valid_d[p]==1 and read_addr_d[p]==read_addr_d[0]:
                    tforward[:] = p
        ts_forward.next = tforward


    @always_comb
    def memTsRdata():
        if ts_forward_d[ts_latency] > 0:
            last_ts_1.next  = write_ts_1_d[ts_forward_d[ts_latency]]
            last_ts_2.next  = write_ts_2_d[ts_forward_d[ts_latency]]
        else:
            last_ts_1.next  = ts_1
            last_ts_2.next  = ts_2
    
        
    @always_comb
    def deltaTs():
        if new_ts_1 > last_ts_1:
            delta_ts_1.next = new_ts_1 - last_ts_1
        else:
            delta_ts_1.next = new_ts_1+MAX_TICK_CNT-last_ts_1

        if new_ts_2 > last_ts_2:
            delta_ts_2.next = new_ts_2 - last_ts_2
        else:
            delta_ts_2.next = new_ts_2+MAX_TICK_CNT-last_ts_2


    # One pipeline before calculating current tokens
    add_token_1_d1  = copySignal(add_token_1)
    delta_ts_1_d1   = copySignal(delta_ts_1)
    
    add_token_2_d1  = copySignal(add_token_2)
    delta_ts_2_d1   = copySignal(delta_ts_2)
    @always(clk.posedge, rstn.negedge)
    def tstkPip():
        if rstn == 0:
            add_token_1_d1.next = 0
            delta_ts_1_d1.next = 0
            
            add_token_2_d1.next = 0
            delta_ts_2_d1.next = 0
        else:
            add_token_1_d1.next = add_token_1
            delta_ts_1_d1.next = delta_ts_1
            
            add_token_2_d1.next = add_token_2
            delta_ts_2_d1.next = delta_ts_2


    sply_token_1  = Signal(intbv(0, min=0, max=2**bucket_w*2))
    sply_token_2  = Signal(intbv(0)[bucket_w:0])
    @always_comb
    def feed1():
        tmp_1 = intbv(0)[bucket_w+tcnt_w:0]
        tmp_2 = intbv(0)[bucket_w+tcnt_w:0]        
        tmp_1[:] = add_token_1_d1 * delta_ts_1_d1
        tmp_2[:] = add_token_2_d1 * delta_ts_2_d1
        if tmp_1 > MAX_CAP_1:
            sply_token_1.next = MAX_CAP_1
        else:
            sply_token_1.next = tmp_1
            
        if tmp_2 > MAX_CAP_2:
            sply_token_2.next = MAX_CAP_2
        else:
            sply_token_2.next = tmp_2


    @always(clk.posedge, rstn.negedge)
    def splypip():
        if rstn == 0:
            osply_token_1.next = 0
            osply_token_2.next = 0
        else:
            osply_token_1.next = sply_token_1
            osply_token_2.next = sply_token_2
        
    @always_comb
    def writetokens():
        conf_itokens.next   = concat(itoken_2, itoken_1)
        
        shadow_write_enable.next = read_valid_d[pipe_ts_tot]
        shadow_write_addr.next = read_addr_d[pipe_ts_tot]
        shadow_itimestamp.next = concat(new_ts_2_d1, new_ts_1_d1)


    @always_comb
    def memRen():

        setup_read_enable.next = read_valid
        
        if forward == 0:
            token_read_enable.next = read_valid
        else:
            token_read_enable.next = 0
    

    return instances()    
    
            
