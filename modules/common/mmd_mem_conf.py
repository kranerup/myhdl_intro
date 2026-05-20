from myhdl import *
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register import register
from modules.conf.mem_cpu_if import mem_cpu_if
from modules.common.Common import copySignal, pass_through, listType, flop, OR, pipeline
from modules.common.memory import memory_init

import sys
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()

def mmd_mem_conf(
        read_valid,
        read_addr,
        
        token_read_enable,
        setup_read_enable,
        
        timestamp_write_enable,
        timestamp_write_addr,
        itimestamp,

        conf_otokens,
        conf_oconfig,
        conf_oreset,

        otimestamp,

        token_write_valid,
        token_write_addr,
        conf_itokens,
        
        doing_init,
        clk,rstn,
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
        bus_settings,
        parallel_buckets,
        token_w,
        bucket_w,
        ifg_w,
        ticks_w,
        depth,
        desc_w,
        desc_d,
        desc_name,
        doc_group,
        conf_type,
        algo_latency,
        default_cap = 1024,
        default_tok = 1,
        default_tic = 0,
        default_ifg = 20,
        ss_id  = 0,
        ss_max = 0,
        name = ""):

    doc_name = desc_name #"%s slice%s" % (desc_name, ss_id)
    reg_name = desc_name.lower().replace(" ", "_")


    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
    conf_doing_init     = []

    zPs = []
    # Method for growing the lists of conf signals when a new block configuration bus is added 
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))

    const_reset  = Signal(intbv(0)[1:0])
    tied_to_gnd  = Signal(intbv(0)[1:0])

    write_conf_reset = Signal(intbv(0)[1:0])
    zPsReset = pass_through(const_reset, write_conf_reset, name=name+".rst")

    CAP_DEFAULT  = default_cap
    TOK_DEFAULT  = default_tok
    TIC_DEFAULT  = default_tic
    IFG_DEFAULT  = default_ifg
    if not listType(default_cap):
        CAP_DEFAULT  = [ default_cap for _ in range(parallel_buckets) ]
    if not listType(default_tok):
        TOK_DEFAULT  = [ default_tok for _ in range(parallel_buckets) ]
    if not listType(default_tic):
        TIC_DEFAULT  = [ default_tic for _ in range(parallel_buckets) ]
    if not listType(default_ifg):
        IFG_DEFAULT  = [ default_ifg for _ in range(parallel_buckets) ]
    assert len(CAP_DEFAULT) == parallel_buckets, "len(CAP_DEFAULT) %s != parallel_buckets %s" % (len(CAP_DEFAULT), parallel_buckets)
    assert len(TOK_DEFAULT) == parallel_buckets, "len(TOK_DEFAULT) %s != parallel_buckets %s" % (len(TOK_DEFAULT), parallel_buckets)
    assert len(TIC_DEFAULT) == parallel_buckets, "len(TIC_DEFAULT) %s != parallel_buckets %s" % (len(TIC_DEFAULT), parallel_buckets)
    assert len(IFG_DEFAULT) == parallel_buckets, "len(IFG_DEFAULT) %s != parallel_buckets %s" % (len(IFG_DEFAULT), parallel_buckets)
    print("CAP_DEFAULT", CAP_DEFAULT)
    print("TOK_DEFAULT", TOK_DEFAULT)
    print("TIC_DEFAULT", TIC_DEFAULT)
    print("IFG_DEFAULT", IFG_DEFAULT)
        
    
    # Bucket configuration
    cBsetTab = conf.CTable(
        name        = 'r_%s_bucket_config' % (reg_name),
        doc_name    = '%s Token Bucket Configuration' % doc_name,
        doc_group   = doc_group,
        regtype     = conf_type,
        description = 'Configuration options for token buckets used by %s. Each entry refers to either a single rate three color marker (srTCM) or a two rate three color marker (trTCM) with two token buckets. For each token bucket the rate is configured by filling in a certain number of tokens at one of the available frequencies. Token bucket 0 shall always use the committed information rate (CIR).'%doc_name,
        access      = 'rw',
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max)
    cBsetReg = conf.CRegister(
        name        = 'r_%s_bucket_config' % (reg_name),
        doc_name    = '%s Token Bucket Configuration' % doc_name,
        doc_group   = doc_group,
        description = 'Configuration options for token buckets used by %s. Each entry refers to either a single rate three color marker (srTCM) or a two rate three color marker (trTCM) with two token buckets. For each token bucket the rate is configured by filling in a certain number of tokens at one of the available frequencies. Token bucket 0 shall always use the committed information rate (CIR).'%doc_name,
        access      = 'rw',
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max,
        index   = desc_d,
        depth   = depth)


    # Bucket token status
    cResetTab = conf.CTable(
        name        = 'r_%s_bucket_reset' % (reg_name),
        doc_name    = '%s Reset' % doc_name,
        doc_group   = doc_group,
        regtype     = conf_type,
        description = 'Reset token buckets so that it is full of tokens again. It is helpful when the token bucket configuration is changed during runtime. Every metering process will clear the reset status in the corresponding entry to validate metering for subsequent traffic.',
        access      = 'rw',
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max)
    cResetReg = conf.CRegister(
        name        = 'r_%s_bucket_reset' % (reg_name),
        doc_name    = '%s Reset' % doc_name,
        doc_group   = doc_group,
        description = 'Reset token buckets so that it is full of tokens again. It is helpful when the token bucket configuration is changed during runtime. Every metering process will clear the reset status in the corresponding entry to validate metering for subsequent traffic.',
        access      = 'rw',
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max,
        index   = desc_d,
        depth   = depth)


    # Number of tokens
    cTokenTab = conf.CTable(
        name        = 'r_%s_bucket_tokens' % (reg_name),
        doc_name    = '%s Current Size' % doc_name,
        doc_group   = doc_group,
        regtype     = conf_type,
        description = 'Number of tokens currently in the token bucket.',
        access      = 'r',
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max)
    cTokenReg = conf.CRegister(
        name        = 'r_%s_bucket_tokens' % (reg_name),
        doc_name    = '%s Current Size' % doc_name,
        doc_group   = doc_group,
        description = 'Number of tokens currently in the token bucket.',
        access      = 'r',
        index   = desc_d,
        depth   = depth,
        doc_cur_ss  = ss_id,
        doc_max_ss  = ss_max)


    for i in range(parallel_buckets):

        cCapField = conf.CField(
            name          = 'bucketCapacity_%d'%(i),
            width         = bucket_w,
            description   = 'Capacity for token bucket %d.'%(i),
            short_name    = 'cap',
            default_value = CAP_DEFAULT[i])

        cTokenField = conf.CField(
            name          = 'tokens_%d'%(i),
            width         = token_w,
            description   = 'Number of tokens added each tick for token bucket %d.'%(i),
            short_name    = 'tok',
            default_value = TOK_DEFAULT[i])
        
        cTickField =  conf.CField(
            name          = 'tick_%d'%(i),
            width         = ticks_w,
            description   = 'Select one of the %d available ticks for token bucket %d. The tick frequencies are configured globaly in the Core Tick Configuration register.' % (hwconf.tick['nr_of_ticks'], i),
            short_name    = 'tic',
            default_value = TIC_DEFAULT[i])

        cBsetReg.append(cCapField)
        cBsetReg.append(cTokenField)
        cBsetReg.append(cTickField)


        cTokenField = conf.CField(
            name          = 'tokens_%d'%(i),
            width         = bucket_w,
            default_value = CAP_DEFAULT[i],
            description   = 'Number of tokens after the last visit for token bucket %d.'%(i))
        cTokenReg.append(cTokenField)


    cResetField = conf.CField(
        name          = 'bucketReset',
        width         = 1,
        default_value = 1,
        description   = 'if set, reload with full tokens for token buckets in this entry.')
    cResetReg.append(cResetField)

        
    cModeField = conf.CField(
        name          = 'bucketMode',
        width         = 1,
        description   = '\\tabTwo{srTCM}{trTCM}')


    cColorField = conf.CField(
        name          = 'colorBlind',
        width         = 1,
        description   = '\\tabTwo{color-aware: The metering result is based on the initial coloring from the ingress process pipeline.}{color-blind: The metering ignores any pre-coloring.}')


    cDropField = conf.CField(
        name          = 'dropMask',
        width         = 3,
        description   = 'Drop mask for the three colors obtained from the metering result. For each bit set to 1 the corresponding color shall drop the packet. Bit 0, 1, 2 represents drop or not for green, yellow and red respectively',
        default_value = 0b100)

    cIfgModeField = conf.CField(
        name          = 'byteCorrectionMode',
        width         = 1,
        description   = '\\tabTwo{Add extra bytes for metering.}{Substract extra bytes for metering.}',
        default_value = 0)
 
    cIfgField = conf.CField(
        name          = 'byteCorrection',
        width         = ifg_w,
        description   = 'Extra bytes per packet to correct for IFG.',
        short_name    = 'ifg',
        default_value = IFG_DEFAULT[i])


    cBsetReg.append(cModeField)
    cBsetReg.append(cColorField)
    cBsetReg.append(cDropField)
    cBsetReg.append(cIfgModeField)
    cBsetReg.append(cIfgField)
    
    cBsetTab.append(cBsetReg)
    cResetTab.append(cResetReg)
    cTokenTab.append(cTokenReg)
    
    bus_settings.append(cBsetTab)
    bus_settings.append(cResetTab)
    bus_settings.append(cTokenTab)    
        
    mem_otokens = copySignal(conf_otokens)
    mem_oconfig = copySignal(conf_oconfig)
    mem_oreset  = copySignal(conf_oreset)
    mem_otimestamp = copySignal(otimestamp)


    @always_comb
    def memRead():
        conf_otokens.next = mem_otokens
        conf_oconfig.next = mem_oconfig
        conf_oreset.next  = mem_oreset
        otimestamp.next   = mem_otimestamp

    ####


    dummy_config_idata = copySignal(mem_oconfig)
    dummy_conf_waddr   = copySignal(read_addr)
    dummy_conf_we      = copySignal(read_valid)
    zPs.append(pass_through(tied_to_gnd, dummy_conf_we, name=name+".cwe"))

    append_conf_signal() # Grow the conf reply bus
    conf_doing_init.append(Signal(intbv(0)[1:0]))
    iMemConfig  =  mem_cpu_if(
        request_address         = request_address,
        request_data            = request_data,
        request_id              = request_id,
        request_type            = request_type,
        request_re              = request_re,
        request_we              = request_we,
        reply_data              = conf_reply_data[-1],
        reply_id                = conf_reply_id[-1],
        reply_status            = conf_reply_status[-1],
        doing_init              = conf_doing_init[-1],
        clk                     = clk,
        rstn                    = rstn,
        settings                = cBsetTab,
        hw_re                   = setup_read_enable,
        hw_raddr                = read_addr,
        hw_odata                = mem_oconfig,
        hw_we                   = dummy_conf_we,
        hw_waddr                = dummy_conf_waddr,
        hw_idata                = dummy_config_idata,
        input_flops             = hwconf.memory_input_flops,
        output_flops            = hwconf.memory_output_flops,
        name                    = name+".config")


    append_conf_signal() # Grow the conf reply bus
    conf_doing_init.append(Signal(intbv(0)[1:0]))        
    iMemToken  =  mem_cpu_if(
        request_address         = request_address,
        request_data            = request_data,
        request_id              = request_id,
        request_type            = request_type,
        request_re              = request_re,
        request_we              = request_we,
        reply_data              = conf_reply_data[-1],
        reply_id                = conf_reply_id[-1],
        reply_status            = conf_reply_status[-1],
        doing_init              = conf_doing_init[-1],
        clk                     = clk,
        rstn                    = rstn,
        settings                = cTokenTab,
        hw_re                   = token_read_enable,
        hw_raddr                = read_addr,
        hw_odata                = mem_otokens,
        hw_we                   = token_write_valid,
        hw_waddr                = token_write_addr,
        hw_idata                = conf_itokens,
        input_flops             = hwconf.memory_input_flops,
        output_flops            = hwconf.memory_output_flops,
        name                    = name+".config")


    append_conf_signal() # Grow the conf reply bus
    conf_doing_init.append(Signal(intbv(0)[1:0]))        
    iMemReset  =  mem_cpu_if(
        request_address         = request_address,
        request_data            = request_data,
        request_id              = request_id,
        request_type            = request_type,
        request_re              = request_re,
        request_we              = request_we,
        reply_data              = conf_reply_data[-1],
        reply_id                = conf_reply_id[-1],
        reply_status            = conf_reply_status[-1],
        doing_init              = conf_doing_init[-1],
        clk                     = clk,
        rstn                    = rstn,
        settings                = cResetTab,
        hw_re                   = read_valid,
        hw_raddr                = read_addr,
        hw_odata                = mem_oreset,
        hw_we                   = timestamp_write_enable,
        hw_waddr                = timestamp_write_addr,            
        hw_idata                = write_conf_reset,
        input_flops             = hwconf.memory_input_flops,
        output_flops            = hwconf.memory_output_flops,
        name                    = name+".config")


    # Timestamp mem, not connected to conf bus
    conf_doing_init.append(Signal(intbv(0)[1:0]))        
    iTsMem = memory_init(
        renable   = read_valid,
        raddr     = read_addr,
        odata     = mem_otimestamp,
        wenable   = timestamp_write_enable,
        waddr     = timestamp_write_addr,
        idata     = itimestamp,
        soft_reset= 0,
        doing_init = conf_doing_init[-1],
        clk       = clk,
        rstn      = rstn,
        depth     = depth,
        reset_value = 0,
        write_through = 1,
        input_flops = hwconf.memory_input_flops,
        output_flops = hwconf.memory_output_flops,
        name      = name+'timestampMem')


    
    zOrinit = OR(conf_doing_init, None, doing_init, name=name+"conforinit")

    # conf_bus_collector should be instantiated when no more append_conf_signal()
    iCollector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.collecotr')
    
    return instances()


    
