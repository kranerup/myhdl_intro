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

def mmd_conf(
        read_valid,
        read_addr,

        read_conf_tokens,
        read_conf_config,
        read_conf_reset,
        read_timestamp,

        write_valid,
        write_addr,
        write_conf_tokens,
        write_timestamp,
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


    nr_of_slices  = len(read_valid)

    if algo_latency > 1:
        print("%s: ERROR! algo_latency (=%d) can only be 0 or 1!"%(name, algo_latency))
        assert False


    doc_name = desc_name #"%s slice%s" % (desc_name, ss_id)
    reg_name = desc_name.lower().replace(" ", "_")


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

    const_reset  = Signal(intbv(0)[parallel_buckets:0])
    tied_to_gnd  = Signal(intbv(0)[1:0])

    write_conf_reset = [Signal(intbv(0)[parallel_buckets:0])  for _ in range(nr_of_slices)]
    zPs = []
    for i in range(nr_of_slices):
        zPs.append(pass_through(const_reset, write_conf_reset[i], name=name+".cres"))

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


        cResetField = conf.CField(
            name          = 'bucketReset_%d'%(i),
            width         = 1,
            default_value = 1,
            description   = 'if set to 1, reload with full tokens for token bucket %d.'%(i))
        cResetReg.append(cResetField)

        cTokenField = conf.CField(
            name          = 'tokens_%d'%(i),
            width         = bucket_w,
            default_value = CAP_DEFAULT[i],
            description   = 'Number of tokens after the last visit for token bucket %d.'%(i))
        cTokenReg.append(cTokenField)
        
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
        
    cIfgField = conf.CField(
        name          = 'ifgCorrection',
        width         = ifg_w,
        description   = 'Extra bytes per packet to correct for IFG.',
        short_name    = 'ifg',
        default_value = IFG_DEFAULT[i])


    cBsetReg.append(cModeField)
    cBsetReg.append(cColorField)
    cBsetReg.append(cDropField)
    cBsetReg.append(cIfgField)
    
    cBsetTab.append(cBsetReg)
    cResetTab.append(cResetReg)
    cTokenTab.append(cTokenReg)
    
    bus_settings.append(cBsetTab)
    bus_settings.append(cResetTab)
    bus_settings.append(cTokenTab)    
    
    
    if nr_of_slices == 1:
        
        mem_renable = Signal(intbv(0)[1:0])
        mem_otokens = copySignal(read_conf_tokens[0])
        mem_oconfig = copySignal(read_conf_config[0])
        mem_oreset  = copySignal(read_conf_reset[0])
        mem_otimestamp = copySignal(read_timestamp[0])
        
        flat_read_conf_tokens = copySignal(mem_otokens)
        flat_read_conf_config = copySignal(mem_oconfig)
        flat_read_conf_reset  = copySignal(mem_oreset)
        flat_read_timestamp   = copySignal(mem_otimestamp)

        zPs.append(pass_through(flat_read_conf_tokens, read_conf_tokens[0], name=name+".1"))
        zPs.append(pass_through(flat_read_conf_config, read_conf_config[0], name=name+".2"))
        zPs.append(pass_through(flat_read_conf_reset,  read_conf_reset[0], name=name+".3"))
        zPs.append(pass_through(flat_read_timestamp,   read_timestamp[0], name=name+".4"))
        
        # Manage multi cycle read write
        read_latency = 1 + hwconf.memory_input_flops + hwconf.memory_output_flops
        pipe_depth   = read_latency+algo_latency
        pipe_tot     = pipe_depth+1
        
        if pipe_depth != 1:
            zPip = []
            read_valid_d = [copySignal(read_valid[0])      for _ in range(pipe_tot)]
            read_addr_d  = [copySignal(read_addr[0])       for _ in range(pipe_tot)]
            write_conf_tokens_d = [copySignal(read_conf_tokens[0])  for _ in range(pipe_tot)]
            write_conf_reset_d  = [copySignal(read_conf_reset[0])   for _ in range(pipe_tot)]
            write_timestamp_d = [copySignal(read_timestamp[0])   for _ in range(pipe_tot)]
            forward = Signal(intbv(0, min=0, max=pipe_tot))
            forward_d = [ copySignal(forward) for _ in range(read_latency+1) ]
            
            zPip.append(pipeline(read_valid[0], read_valid_d, clk, rstn, name=name+'.zPipValid'))
            zPip.append(pipeline(read_addr[0], read_addr_d, clk, rstn, name=name+'.zPipAddr'))
            zPip.append(pipeline(write_conf_tokens[0], write_conf_tokens_d, clk, rstn, name=name+'.zPipToken'))
            zPip.append(pipeline(write_conf_reset[0], write_conf_reset_d, clk, rstn, name=name+'.zPipReset'))
            zPip.append(pipeline(write_timestamp[0], write_timestamp_d, clk, rstn, name=name+'.zPipTs'))
            zPip.append(pipeline(forward, forward_d, clk, rstn, name=name+'zPipforward'))

            @always_comb
            def countforw():
                tforward = intbv(0, min=0, max=pipe_tot)
                tforward[:] = 0
                if read_valid_d[0] == 1: # New read, check un-written addresses
                    for p in range(1, pipe_tot):
                        if tforward==0 and read_valid_d[p]==1 and read_addr_d[p]==read_addr_d[0]:
                            tforward[:] = p
                forward.next = tforward

            @always_comb
            def memRen():
                if forward == 0:
                    mem_renable.next = read_valid_d[0]
                else:
                    mem_renable.next = 0

            @always_comb
            def memRdata():
                flat_read_conf_config.next = mem_oconfig # Not writeable
                if forward_d[read_latency] > 0:
                    flat_read_conf_tokens.next = write_conf_tokens_d[forward_d[read_latency]-algo_latency]
                    flat_read_conf_reset.next  = write_conf_reset_d[forward_d[read_latency]-algo_latency]
                    flat_read_timestamp.next   = write_timestamp_d[forward_d[read_latency]-algo_latency]
                else:
                    flat_read_conf_tokens.next = mem_otokens
                    flat_read_conf_reset.next  = mem_oreset
                    flat_read_timestamp.next = mem_otimestamp
        else:
            @always_comb
            def memRead():
                mem_renable.next = read_valid[0]
                
                flat_read_conf_tokens.next = mem_otokens
                flat_read_conf_reset.next  = mem_oreset
                flat_read_timestamp.next = mem_otimestamp

        ####

        
        dummy_config_idata = copySignal(read_conf_config)
        dummy_conf_waddr   = copySignal(read_addr)
        dummy_conf_we      = copySignal(read_valid)
        zPs.append(pass_through(tied_to_gnd, dummy_conf_we, name=name+".we1"))

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
            hw_re                   = mem_renable,
            hw_raddr                = read_addr[0],
            hw_odata                = mem_oconfig,
            hw_we                   = dummy_conf_we[0],
            hw_waddr                = dummy_conf_waddr[0],
            hw_idata                = dummy_config_idata[0],
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
            hw_re                   = mem_renable,
            hw_raddr                = read_addr[0],
            hw_odata                = mem_otokens,
            hw_we                   = write_valid[0],
            hw_waddr                = write_addr[0],
            hw_idata                = write_conf_tokens[0],
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
            hw_re                   = mem_renable,
            hw_raddr                = read_addr[0],
            hw_odata                = mem_oreset,
            hw_we                   = write_valid[0],
            hw_waddr                = write_addr[0],            
            hw_idata                = write_conf_reset[0],
            input_flops             = hwconf.memory_input_flops,
            output_flops            = hwconf.memory_output_flops,
            name                    = name+".config")


        # Timestamp mem, not connected to conf bus
        conf_doing_init.append(Signal(intbv(0)[1:0]))        
        iTsMem = memory_init(
            renable   = mem_renable,
            raddr     = read_addr[0],
            odata     = mem_otimestamp,
            wenable   = write_valid[0],
            waddr     = write_addr[0],
            idata     = write_timestamp[0],
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
    else:

        # No doing_init
        zPs.append(pass_through(tied_to_gnd, doing_init, name=name+".d12"))        
            
        read_all_conf_config = [copySignal(read_conf_config[0]) for _ in range(depth)]
        read_all_conf_tokens = [copySignal(read_conf_tokens[0]) for _ in range(depth)]
        write_all_conf_tokens = [copySignal(read_conf_tokens[0]) for _ in range(depth)]
        all_conf_we    = [Signal(intbv(0)[1:0])  for _ in range(depth)]
        read_all_conf_reset  = [copySignal(read_conf_reset[0])  for _ in range(depth)]
        write_all_conf_reset = [copySignal(read_conf_reset[0])  for _ in range(depth)]


        timestamp_reg  = [copySignal(read_timestamp[0])  for _ in range(depth)]
        

        read_addr_d1 = copySignal(read_addr)

        # Read delays one cycle
        zFlopRead = flop(read_addr, read_addr_d1, clk, rstn)

        if algo_latency == 0:
            # No read-write collisions
            @always_comb
            def readOut():
                for i in range(nr_of_slices):
                    read_conf_config[i].next = read_all_conf_config[read_addr_d1[i]]                    
                    read_conf_tokens[i].next = read_all_conf_tokens[read_addr_d1[i]]
                    read_conf_reset[i].next  = read_all_conf_reset[read_addr_d1[i]]
                    read_timestamp[i].next   = timestamp_reg[read_addr_d1[i]]


        else:
                    
            # HW can't rewrite config, read directly
            @always_comb
            def readConfig():
                for i in range(nr_of_slices):
                    read_conf_config[i].next = read_all_conf_config[read_addr_d1[i]]

            # MUX for conf data and write data
            @always_comb
            def readSel():
                for i in range(nr_of_slices):
                    read_conf_tokens[i].next = read_all_conf_tokens[read_addr_d1[i]]
                    read_conf_reset[i].next  = read_all_conf_reset[read_addr_d1[i]]
                    read_timestamp[i].next   = timestamp_reg[read_addr_d1[i]]
                    for j in range(nr_of_slices):
                        if write_valid[j]==1 and write_addr[j]==read_addr_d1[i]:
                            read_conf_tokens[i].next = write_conf_tokens[j]
                            read_conf_reset[i].next  = write_conf_reset[j]
                            read_timestamp[i].next   = write_timestamp[j]
                            
                
        @always_comb
        def writeback():
            for i in range(depth):
                all_conf_we[i].next = 0
                write_all_conf_tokens[i].next = 0
                write_all_conf_reset[i].next = 0
            for i in range(nr_of_slices):
                all_conf_we[write_addr[i]].next = write_valid[i]
                write_all_conf_tokens[write_addr[i]].next = write_conf_tokens[i]
                

        @always(clk.posedge, rstn.negedge)
        def writeTs():
            if rstn == 0:
                for i in range(depth):
                    timestamp_reg[i].next = 0
            else:
                for i in range(nr_of_slices):
                    if write_valid[i] == 1:
                        timestamp_reg[write_addr[i]].next = write_timestamp[i]



                
        append_conf_signal() # Grow the conf reply bus
        iTabConfig  =  register(
            request_address         = request_address,
            request_data            = request_data,
            request_id              = request_id,
            request_type            = request_type,
            request_re              = request_re,
            request_we              = request_we,
            reply_data              = conf_reply_data[-1],
            reply_id                = conf_reply_id[-1],
            reply_status            = conf_reply_status[-1],
            clk                     = clk,            
            rstn                    = rstn,           
            settings                = cBsetTab,
            register_read           = read_all_conf_config,
            name                    = name+".config")


        append_conf_signal() # Grow the conf reply bus
        iTabToken  =  register(
            request_address         = request_address,
            request_data            = request_data,
            request_id              = request_id,
            request_type            = request_type,
            request_re              = request_re,
            request_we              = request_we,
            reply_data              = conf_reply_data[-1],
            reply_id                = conf_reply_id[-1],
            reply_status            = conf_reply_status[-1],
            clk                     = clk,            
            rstn                    = rstn,           
            settings                = cTokenTab,
            register_read           = read_all_conf_tokens,
            register_write          = write_all_conf_tokens,
            register_we             = all_conf_we,
            name                    = name+".tokens")


        append_conf_signal() # Grow the conf reply bus
        iTabReset  =  register(
            request_address         = request_address,
            request_data            = request_data,
            request_id              = request_id,
            request_type            = request_type,
            request_re              = request_re,
            request_we              = request_we,
            reply_data              = conf_reply_data[-1],
            reply_id                = conf_reply_id[-1],
            reply_status            = conf_reply_status[-1],
            clk                     = clk,            
            rstn                    = rstn,           
            settings                = cResetTab,
            register_read           = read_all_conf_reset,
            register_write          = write_all_conf_reset,
            register_we             = all_conf_we,
            name                    = name+".reset")


    # conf_bus_collector should be instantiated when no more append_conf_signal()
    iCollector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.collecotr')
    
    return instances()


    
