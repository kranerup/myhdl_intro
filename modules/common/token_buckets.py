from myhdl import *
from modules.conf.conf_bus_collector import conf_bus_collector
from modules.conf import conf
from modules.conf.register_table import register_table
from modules.conf.register import register
from modules.common.Common import copySignal, pass_through, listType, flop
import math

import sys
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()

def list2pair(l):
    return [[i, l[i]] for i in range(len(l))]
def format_default(d):
    if not listType(d):
        return d
    else:
        return {'resetValue':max(d), 'list':list2pair(d)}

def token_buckets(
        ibytes,
        ipkts,
        status_rd,
        request_address, request_data,request_id,request_type,request_re,request_we,
        reply_data,reply_id,reply_status,bus_settings,
        tick,
        clk,
        rstn,
        fill_mask = None,
        pcnt_edge = None,        
        iindex    = None,
        status_re = None,
        status_ra = None,
        status_latency = None,
        bucket_w = 16,
        token_w  = 11,
        ifg_w    = 8,
        depth    = 1,
        desc_w = "Egress Ports",
        desc_d = "",
        desc_name = "MBSC",
        doc_group = "Token Buckets",
        default_cap = 1024,
        default_pnb = 1, 
        default_tok = 1,
        default_tic = 0,
        default_thr = 512,
        default_ifg = 24,
        avb_mode = False,
        avail = None,
        ss_id  = 0,
        ss_max = 0,
        force_no_debug = 0,
        name = ''
    ):

    CAP_REG = 'bucketCapacity' in hwconf.token_bucket_debug
    CAP_SINGLE = False
    if CAP_REG:
        CAP_SINGLE = hwconf.token_bucket_debug['bucketCapacity'] == "single"
    THR_REG = 'threshold' in hwconf.token_bucket_debug
    THR_SINGLE = False
    if THR_REG:
        THR_SINGLE = hwconf.token_bucket_debug['threshold'] == "single"
    VAL_REG = 'currentVal' in hwconf.token_bucket_debug
   
    assert iindex==None and status_re==None and status_ra==None and status_latency==None and depth==1, "ERROR! token buckets do not yet support depth>1" 
    
    def append_conf_signal():
        conf_reply_data.append(   copySignal(reply_data))
        conf_reply_id.append(     copySignal(reply_id))
        conf_reply_status.append( copySignal(reply_status))

    logic_high = Signal(intbv(1)[1:0])
    logic_low  = Signal(intbv(0)[1:0])
    # Configuration reply data channels from the configured blocks
    conf_reply_data     = []
    conf_reply_id       = []
    conf_reply_status   = []
    
    # Interface to the CPU Bus
    
    nr_of_buckets = len(ibytes)
    nr_of_ticks   = len(tick)
    ticks_w       = (nr_of_ticks-1).bit_length()
    bytes_w = (hwconf.cell_size//8).bit_length()
    
    if fill_mask == None or not avb_mode:
        fill_mask_mode = 0
        fill_mask_signal = Signal(intbv((1<<nr_of_buckets)-1)[nr_of_buckets:])        
    else:
        assert len(fill_mask) == nr_of_buckets, "ERROR! len(fill_mask) %s != nr_of_buckets %s" % (len(fill_mask), nr_of_buckets)
        fill_mask_mode = 1
        fill_mask_signal = fill_mask
            
    if not avb_mode:
        avail_sig = Signal(intbv(0)[nr_of_buckets:])
        tick_name = "core"
    else:
        avail_sig = avail
        tick_name = "PTP"
        
    CAP_MAX = 1<<bucket_w-1
    
    def makelist(i):
        if not listType(i):
            return [i for _ in range(nr_of_buckets)]
        return i        
    
    CAP_DEFAULT = makelist( default_cap )
    THR_DEFAULT = makelist( default_thr )
    TOK_DEFAULT = makelist( default_tok )
    TIC_DEFAULT = makelist( default_tic )
    PNB_DEFAULT = makelist( default_pnb )
    IFG_DEFAULT = makelist( default_ifg )
    print("CAP_DEFAULT", CAP_DEFAULT)
    print("THR_DEFAULT", THR_DEFAULT)
    print("TOK_DEFAULT", TOK_DEFAULT)
    print("TIC_DEFAULT", TIC_DEFAULT)
    print("PNB_DEFAULT", PNB_DEFAULT)
    print("IFG_DEFAULT", IFG_DEFAULT)
        
    print("Instanciated token_buckets %s with bucket_w %s, token_w %s, and nr_of_buckets %s, avb_mode %s. " % (name, bucket_w, token_w, nr_of_buckets, avb_mode))

    # Internal register Mapping
    
    reg_cap     = [ Signal( intbv(0)[ bucket_w:  ]) for i in range(nr_of_buckets)]
    reg_bval    = [ Signal( intbv(0)[ bucket_w:  ]) for _ in range(nr_of_buckets)]
    reg_avb     = [ Signal( intbv(0)[ 1:         ]) for _ in range(nr_of_buckets)]
    reg_pnb     = [ Signal( intbv(0)[ 1:         ]) for _ in range(nr_of_buckets)]
    reg_tok     = [ Signal( intbv(0)[ token_w:   ]) for _ in range(nr_of_buckets)]
    reg_tic_raw = [ Signal( intbv(0)[ ticks_w:   ]) for _ in range(nr_of_buckets)]
    reg_tic     = [ Signal( intbv(0)[ ticks_w:   ]) for _ in range(nr_of_buckets)]
    reg_thr     = [ Signal( intbv(0)[ bucket_w:  ]) for i in range(nr_of_buckets)]
    reg_ifg     = [ Signal( intbv(0)[ ifg_w:     ]) for _ in range(nr_of_buckets)]
    if not force_no_debug: # Used in the module-split IPP
        reg_stat    =   Signal( intbv(0)[ nr_of_buckets: ], debug_level = 1)
    else:
        reg_stat    =   Signal( intbv(0)[ nr_of_buckets: ])
        
    reg_enable  =   Signal( intbv(0)[ nr_of_buckets: ])

    next_bval    = [ Signal( intbv(0)[ bucket_w:  ]) for _ in range(nr_of_buckets)]
    next_stat    =   Signal( intbv(0)[ nr_of_buckets: ])
    zBucket = []
    
    bsettings_read = []

    rsettings_read = []

    buckets_read = []
    buckets_write = []
    buckets_write_en = []

    misc_read = []
    misc_write = []
    misc_write_en = []

    doc_name = desc_name #"%s slice%s" % (desc_name, ss_id)
    int_name = doc_name

    if ss_max == 0:
        ss = ""
    else:
        ss = "_ss%s"%ss_id
    int_name = int_name.lower().replace(" ", "_")
    reg_name = desc_name.lower().replace(" ", "_")
    
    reg_rsettings = conf.CTable(
        name           = int_name+"_rate_settings%s"%ss,
        description    = 'For each %s there is a Token Bucket which can count either in terms of Packets or Bytes (PNB). For each bucket you can configure the rate at which tokens are added (RATE/TICK).' % desc_w,
        regtype        = 'reg',
        fw_write_ports = 0,
        fw_read_ports  = 0
    )
    reg_misc = conf.CTable(
        name           = int_name+"_misc%s"%ss,
        description    = '',
        regtype        = 'reg',
        fw_write_ports = 0,
        fw_read_ports  = 0
    )
    reg_buckets = conf.CTable(
        name           = int_name+"_values%s"%ss,
        description    = '',
        regtype        = 'reg',
        fw_write_ports = 0,
        fw_read_ports  = 0
    )

    cregw = bucket_w
    tregw = bucket_w
    avb_w = 1 if avb_mode else 0
    rregw = 1 + token_w + ticks_w + ifg_w + avb_w
    if (CAP_REG and not CAP_SINGLE) or (THR_REG and not THR_SINGLE):
        reg_bsettings = conf.CTable(
            name           = int_name+"_bucket_settings%s"%ss,
            description    = 'For each bucket you can configure the capacity (CAP) and the theshold (THR) at which the bucket will switch from ACCEPT to DENY.',
            regtype        = 'reg',
            fw_write_ports = 0,
            fw_read_ports  = 0
        )
    if CAP_REG:
        if CAP_SINGLE:
            nreg = 1
        else:
            nreg = nr_of_buckets
        inst_creg = conf.CRegister(
            doc_name  = '%s Bucket Capacity Configuration' % doc_name,
            doc_group = doc_group,
            name = 'rg_%s_bucket_cap' % (reg_name),
            index = desc_w,
            description = 'Token Bucket Capacity Configuration for %s' % doc_name,
            doc_cur_ss = ss_id,
            doc_max_ss = ss_max,
            depth = nreg)
        inst_creg.append( conf.CField(
            name          = 'bucketCapacity',
            width         = bucket_w,
            description   = 'Capacity of the token bucket',
            short_name    = 'cap',
            default_value = max(CAP_DEFAULT) if CAP_SINGLE else format_default( CAP_DEFAULT ),
            valid_data    = None,
            access        = 'rw'))

        if not CAP_SINGLE:
            reg_bsettings.append(inst_creg)
            for i in range(nreg):
                bsettings_read.append( Signal( intbv(0)[ cregw:0 ] ))
                zBucket.append(pass_through(bsettings_read[-1], [
                    reg_cap[i]
                ], name=name+".bsr")) 
        else:
            reg_misc.append(inst_creg)
            misc_read.append(  inst_creg.fields[-1].get_signal() ) 
            misc_write.append( inst_creg.fields[-1].get_signal() )
            misc_write_en.append( Signal( intbv(0)[ 1:0 ]))
            zBucket.append( pass_through( logic_low, misc_write_en[-1], name=name+".llwe"))
            for i in range(nr_of_buckets):
                zBucket.append( pass_through( misc_read[-1], reg_cap[i], name=name+".cap%s"%i))
    else:
        zPassdefcap=[]
        for i in range(nr_of_buckets):
            zPassdefcap.append(pass_through(CAP_MAX, reg_cap[i], name=name+".zPassdefcap%s"%i))
        
    if THR_REG:
        if THR_SINGLE:
            nreg = 1
        else:
            nreg = nr_of_buckets
        inst_treg = conf.CRegister(
            doc_name  = '%s Bucket Threshold Configuration' % doc_name,
            doc_group = doc_group,
            name = 'rg_%s_bucket_thr' % (reg_name),
            index = desc_w,
            description = 'Token Bucket Threshold Configuration for %s' % doc_name,
            doc_cur_ss = ss_id,
            doc_max_ss = ss_max,
            depth = nreg)
        inst_treg.append( conf.CField(
            name          = 'threshold',
            width         = bucket_w,
            description   = 'Minimum number of tokens in bucket for the status to be set to accept.',
            short_name    = 'thr',
            default_value = max(THR_DEFAULT) if THR_SINGLE else format_default( THR_DEFAULT ),
            valid_data    = None,
            access        = 'rw'))
        if not THR_SINGLE:
            reg_bsettings.append(inst_treg)
            for i in range(nreg):
                bsettings_read.append(  Signal( intbv(0)[ tregw:0 ] ))
                zBucket.append(pass_through(bsettings_read[-1], [
                    reg_thr[i]
                ], name=name+".bst"))
        if THR_SINGLE:
            reg_misc.append(inst_treg)
            misc_read.append(  inst_treg.fields[-1].get_signal() ) 
            misc_write.append( inst_treg.fields[-1].get_signal() )
            misc_write_en.append( Signal( intbv(0)[ 1:0 ]))
            zBucket.append( pass_through( logic_low, misc_write_en[-1], name=name+".llwe2"))
            for i in range(nr_of_buckets):
                zBucket.append( pass_through( misc_read[-1], reg_thr[i], name=name+".thr%s"%i))
    else:
        zPassdefthr=[]
        for i in range(nr_of_buckets):
            zPassdefthr.append(pass_through(THR_DEFAULT[i], reg_thr[i], name=name+".zPassdefthr%s"%i))
            
    from num2words import num2words
    inst_rreg = conf.CRegister(
        doc_name  = '%s Rate Configuration' % doc_name,
        doc_group = doc_group,
        name = 'rg_%s_rate' % (reg_name),
        index = desc_w,
        description = 'Token Bucket rate Configuration for %s' % doc_name,
        doc_cur_ss = ss_id,
        doc_max_ss = ss_max,
        depth = nr_of_buckets)
    inst_rreg.append( conf.CField(
        name          = 'packetsNotBytes',
        width         = 1,    #   Should be 1 bit only
        description   = 'If set the bucket will count packets, if cleared bytes',
        short_name    = 'pnb',
        default_value = format_default( PNB_DEFAULT ),
        valid_data    = None,
        access        = 'rw'))
    inst_rreg.append( conf.CField(
        name          = 'tokens',
        width         = token_w,
        description   = 'The number of tokens added each tick',
        short_name    = 'tok',
        default_value = format_default( TOK_DEFAULT ),
        valid_data    = None,
        access        = 'rw'))
    inst_rreg.append( conf.CField(
        name          = 'tick',
        width         = ticks_w,
        description   = 'Select one of the %s available %s ticks. The tick frequencies are configured globaly in the %s Tick Configuration register.' % (num2words(hwconf.tick['nr_of_ticks']), tick_name, tick_name),
        short_name    = 'tic',
        default_value = format_default( TIC_DEFAULT ),
        valid_data    = None,
        access        = 'rw'))
    inst_rreg.append( conf.CField(
        name          = 'ifgCorrection',
        width         = ifg_w,
        description   = 'Extra bytes per packet to correct for IFG in byte mode. Default is 4 byte FCS plus 20 byte IFG.',
        short_name    = 'ifg',
        default_value = format_default( IFG_DEFAULT ),
        valid_data    = None,
        access        = 'rw'))
    if avb_mode:
        if fill_mask_mode:
            fill_text = "and the bucket will not receive any tokens while the output is gated by the egress transmission gate."
        else:
            fill_text = ""
        inst_rreg.append( conf.CField(
            name          = 'avb',
            width         = 1,    #   Should be 1 bit only
            description   = 'If set the bucket will work in AVB-mode. That is, the bucket will be set to the threshold level when there are no packets queued%s.' % fill_text,
            short_name    = 'avb',
            default_value = 0,
            valid_data    = None,
            access        = 'rw'))            
    reg_rsettings.append(inst_rreg)

    for i in range(nr_of_buckets):
        rsettings_read.append(  Signal( intbv(0)[ rregw:0 ] ))
        settings_list = [
            reg_pnb[i],
            reg_tok[i],
            reg_tic_raw[i],
            reg_ifg[i]
        ]
        if avb_mode:
            print("%s avb-mode" % name)
            settings_list.append(reg_avb[i])
        zBucket.append(flop(rsettings_read[-1], settings_list, clk, rstn, name=name+".rsr"))


    @always_comb
    def tickFilt():
        for i in range(nr_of_buckets):
            if reg_tic_raw[i] < nr_of_ticks:
                reg_tic[i].next = reg_tic_raw[i]
            else:
                reg_tic[i].next = nr_of_ticks-1


    if VAL_REG:
        inst_reg_bval = conf.CRegister(
            doc_name  = '%s Current Size' % doc_name,
            doc_group = doc_group,
            doc_cur_ss = ss_id,
            doc_max_ss = ss_max,
            name = 'rg_val',
            index = desc_w,
            attributes = ['no_default_check'],
            access = 'r',
            depth = nr_of_buckets,
            description = 'Number of tokens currently in the token bucket.')
        valF = conf.CField(
            name          = 'currentVal',
            width         = bucket_w,
            description   = 'Number of tokens currently in the token bucket for this %s' % desc_w,
            short_name    = 'val',
            default_value = format_default( THR_DEFAULT ),
            valid_data    = None)
        inst_reg_bval.append(valF)
        reg_buckets.append(inst_reg_bval)

        for j in range(nr_of_buckets):
            buckets_read.append(  Signal( intbv(0)[ bucket_w:0 ] ))
            buckets_write.append( Signal( intbv(0)[ bucket_w:0 ] ))
            buckets_write_en.append( Signal( intbv(1)[ 1:0 ]))
            zBucket.append( pass_through( buckets_read[-1], reg_bval[j], name=name+".br"))
            zBucket.append( pass_through( next_bval[j], buckets_write[-1], name=name+".bw"))
            zBucket.append( pass_through( logic_high, buckets_write_en[-1], name=name+".be"))
    else:
        zFlopbval = []
        for i in range(len(reg_bval)):
            zFlopbval.append(flop(next_bval[i], reg_bval[i], clk, rstn, reset_value=THR_DEFAULT[i], name=name+".zFlopbval%s"%i))

    # One On/Off register with bits = nr_of_ports
    inst_reg_on = conf.CRegister(
        doc_name = '%s Enable' % doc_name,
        doc_group = doc_group,
        doc_cur_ss = ss_id,
        doc_max_ss = ss_max,
        name  = 'rg_%s_enable' % reg_name,
        description = 'Bitmask to turn %s ON/OFF (1/0) for %s' %(doc_name, desc_w),
        access        = 'rw',
        depth = 1)
    inst_field_on = conf.CField(
        name          = 'enable',
        width         = nr_of_buckets,
        description   = 'Bitmask where the index is the %s' % desc_w,
        short_name    = 'bm',
        default_value = 0,
        valid_data    = None)

    inst_reg_on.append(inst_field_on)
    reg_misc.append(inst_reg_on)
    
    misc_read.append(  Signal( intbv(0)[ nr_of_buckets:0 ]))
    misc_write.append( Signal( intbv(0)[ nr_of_buckets:0 ]))
    misc_write_en.append( Signal( intbv(0)[ 1:0 ]))
    zBucket.append( pass_through( misc_read[-1], reg_enable, name=name+".mr"))
    zBucket.append( pass_through( logic_low, misc_write_en[-1], name=name+".ll"))
    
    bus_settings.append(reg_rsettings)
    append_conf_signal()
    iRsettings = register(
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
        reg_rsettings,
        rsettings_read,
        name = name+".iRsettings")

    if (CAP_REG and not CAP_SINGLE) or (THR_REG and not THR_SINGLE):
        bus_settings.append(reg_bsettings)
        append_conf_signal()
        iBsettings = register(
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
            reg_bsettings,
            bsettings_read,
            name = name+".iBsettings")

    if VAL_REG:
        bus_settings.append(reg_buckets)
        append_conf_signal()
        iBuckets = register(
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
            reg_buckets,
            buckets_read,
            buckets_write,
            buckets_write_en,
            name = name+".iBuckets")

    bus_settings.append(reg_misc)
    append_conf_signal()
    iMisc = register(
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
        reg_misc,
        misc_read,
        misc_write,
        misc_write_en,
        name = name+".iMisc")

    iCollector = conf_bus_collector(conf_reply_data, conf_reply_id, conf_reply_status, reply_data, reply_id, reply_status, clk, rstn, bus_settings, name = name+'.iCollector')

    
    init      = Signal(intbv(0)[1:0])
    first_pkt = Signal(intbv(0)[1:0])
    @always(clk.posedge, rstn.negedge)
    def init_process():
        if rstn==0:
            init.next      = 1
            first_pkt.next = 1
        else:
            if init==1:
                init.next = 0
            for i in range(nr_of_buckets):
                if ibytes[i]>0 or ipkts[i]>0:
                    first_pkt.next = 0

    debug_underflow = Signal(intbv(0)[nr_of_buckets:])
    debug_overflow = Signal(intbv(0)[nr_of_buckets:])
                    
    if ibytes[0].min == 0:
        
        token_dec = [ Signal(intbv(0)[(bytes_w+ifg_w):0])  for _ in range(nr_of_buckets)]
        token_inc = copySignal(reg_tok)
        @always(clk.posedge, rstn.negedge)
        def tkDec():
            if rstn == 0:
                for i in range(nr_of_buckets):
                    token_dec[i].next = 0
            else:
                for i in range(nr_of_buckets):
                    if reg_pnb[i] == 0:
                        if ipkts[i] == 1:
                            token_dec[i].next = ibytes[i] + reg_ifg[i]
                        else:
                            token_dec[i].next = ibytes[i]
                    else:
                        token_dec[i].next = ipkts[i]
                        
        @always(clk.posedge, rstn.negedge)
        def tkInc():
            if rstn == 0:
                for i in range(nr_of_buckets):
                    token_inc[i].next = 0
            else:
                for i in range(nr_of_buckets):
                    token_inc[i].next = 0
                    if tick[reg_tic[i]] == 1:                        
                        if fill_mask_mode==1:
                            if fill_mask_signal[i]==0 or reg_avb[i]==0:
                                token_inc[i].next = reg_tok[i]
                        else:
                            token_inc[i].next = reg_tok[i]

        @always_comb
        def update_process():
            debug_underflow.next = 0
            debug_overflow.next = 0
            for i in range(nr_of_buckets):
                if reg_bval[i] >= reg_thr[i] or reg_enable[i]==0:
                    next_stat.next[i] = 1
                else:
                    next_stat.next[i] = 0

                if reg_enable[i]==0 or init==1 or first_pkt==1:
                    next_bval[i].next = reg_thr[i]
                elif reg_bval[i] + token_inc[i] > reg_cap[i] + token_dec[i]:
                    next_bval[i].next = reg_cap[i]
                    debug_overflow.next[i] = 1
                elif reg_bval[i] + token_inc[i] < token_dec[i]:
                    next_bval[i].next = 0
                    debug_underflow.next[i] = 1
                else:
                    next_bval[i].next = reg_bval[i] + token_inc[i] - token_dec[i]
                if avb_mode==1:
                    # In AVB-mode never allow an empty queue to accumulate tokens. 
                    if reg_avb[i]==1 and avail_sig[i]==0 and (reg_bval[i] + token_inc[i] > reg_thr[i] + token_dec[i]):
                        next_bval[i].next = reg_thr[i]
    else:
        maxdiff=(1<<(bucket_w+2))
        mindiff=-(1<<(bucket_w+2))
        if ipkts[0].min >= 0:
            iepkts = [ Signal(intbv(0, min=-ipkts[0].max, max=ipkts[0].max)) for _ in range(nr_of_buckets) ]
        else:
            iepkts = copySignal(ipkts)
            
        iebytes = [  Signal(intbv(0, min=mindiff, max=maxdiff)) for _ in range(nr_of_buckets) ]
        @always_comb
        def sign_extend():
            for i in range(nr_of_buckets):
                iebytes[i].next = ibytes[i]
                iepkts[i].next = ipkts[i]

        diff = [  Signal(intbv(0, min=mindiff, max=maxdiff)) for _ in range(nr_of_buckets) ]
        diff_ff = [  Signal(intbv(0, min=mindiff, max=maxdiff)) for _ in range(nr_of_buckets) ]
        print(f"{hwconf.token_bucket_debug=}")
        if "pipeline_diff" in hwconf.token_bucket_debug:
            print(f"{name} pipeline_diff is set")
            flopdecr = flop(diff, diff_ff, clk, rstn)
        else:
            passdiff = [] 
            for i in range(len(diff)):
                passdiff += [pass_through(diff[i], diff_ff[i], name=name+f".passdiff{i}")]
        
        @always_comb
        def calcdiff():
            decr = modbv(0, min=mindiff, max=maxdiff)
            for i in range(nr_of_buckets):
                diff[i].next = 0
                decr[:] = iepkts[i]
                if reg_pnb[i] == 0:
                    decr[:] = iebytes[i] + iepkts[i]*reg_ifg[i]

                if fill_mask_mode==1:
                    if fill_mask_signal[i]==0 or reg_avb[i]==0:
                        decr[:] = decr - reg_tok[i]*tick[ reg_tic[i] ]
                else:
                    decr[:] = decr - reg_tok[i]*tick[ reg_tic[i] ]
                diff[i].next = decr
                
        
        @always_comb
        def update_process():
            debug_underflow.next = 0
            debug_overflow.next = 0
            tmp = modbv(0, min=mindiff, max=maxdiff)
            for i in range(nr_of_buckets):
                if reg_bval[i] >= reg_thr[i] or reg_enable[i]==0:
                    next_stat.next[i] = 1
                else:
                    next_stat.next[i] = 0

                next_bval[i].next = reg_bval[i]
                tmp[:] = reg_bval[i] - diff_ff[i]
                
                if reg_enable[i]==0 or init==1 or first_pkt==1:
                    next_bval[i].next = reg_thr[i]
                elif tmp > reg_cap[i]:
                    next_bval[i].next = reg_cap[i]
                    debug_overflow.next[i] = 1
                elif tmp < 0:
                    next_bval[i].next = 0
                    debug_underflow.next[i] = 1
                else:
                    next_bval[i].next = tmp[bucket_w:]
                if avb_mode==1:
                    # In AVB-mode never allow an empty queue to accumulate tokens. 
                    if reg_avb[i]==1 and avail_sig[i]==0 and (tmp > reg_thr[i]):
                        next_bval[i].next = reg_thr[i]

    @always(clk.posedge, rstn.negedge)
    def regStat():
        if rstn == 0:
            reg_stat.next = 0
        else:
            reg_stat.next = next_stat
            "synthesis translate_off"
            for i in range(nr_of_buckets):
                if debug_overflow[i]==1:
                    print("%s bucket %s ofl" % (name, i))
                if debug_underflow[i]==1:
                    print("%s bucket %s ufl" % (name, i))
            "synthesis translate_on"
 
                
    flop_stat = flop(reg_stat, status_rd, clk, rstn, name=name+'.flop_stat')
    
    return instances()

# The token bucket registers
class rg_token_buckets(object):
    def __init__(self,C,**kwarg):
        self.cap = intbv(kwarg['cap'])[ C['bucket_w']: ]
        self.pnb = intbv(kwarg['pnb'])[    1: ]
        self.tok = intbv(kwarg['tok'])[ C['token_w']: ]
        self.tic = intbv(kwarg['tic'])[ C['ticks_w']: ]
        self.thr = intbv(kwarg['thr'])[ C['bucket_w']: ]
        self.ifg = intbv(kwarg['ifg'])[ C['ifg_w']: ]
        self.avb = None
        if 'avb' in list(kwarg.keys()):
            if kwarg['avb']!=None:
                self.avb = intbv(kwarg['avb'])[    1: ]
        self.rate = None
        if 'rate' in list(kwarg.keys()):
            self.rate = kwarg['rate']
            
    def get_intbv(self, reg):
        if reg=='cap':
            value = self.cap
        elif reg=='thr':
            value = self.thr
        elif reg=='tic':
            value = self.tic
        elif reg=='avb':
            value = self.avb
        else:
            if self.avb!=None:
                print("rg_token_buckets get_intbv returning in abv-mode", self.avb)
                value = concat(self.avb, self.ifg, self.tic, self.tok, self.pnb)
            else:
                print("rg_token_buckets get_intbv returning in non-abv-mode", self.avb)
                value = concat(self.ifg, self.tic, self.tok, self.pnb)
        return value
    def get_int(self, reg):
        value = int(self.get_intbv(reg))
        return value

def set_rate(rate, pnb, port_bw, hwconf, constants, cap=None, thr=None, ifg_bytes=24, min_thr=None,min_token=None, avb=None, tick="default"):
    print("token_bucket.set_rate tick=%s" % tick) 
    if tick=="default" or tick=="core":
        tick_freq = hwconf.tick_freq("core")
    elif tick=="ptp":
        tick_freq = hwconf.tick_freq("ptp")
    elif tick=="core_freq":
        tick_name = "core_freq"
        tick_freq = [hwconf.core_freq]
        print("token_bucket.set_rate tick=core_freq = %s" % tick_freq)
    elif type(tick) in (int, float):
        tick_freq = [tick]
    else:
        assert False
        
    minLen=60
        
    fullByteRate           = port_bw/8.0
    fullPktRate            = fullByteRate/(minLen+ifg_bytes)

    byteRate = fullByteRate*rate
    pktRate  = fullPktRate*rate

    pktTokenIn         = 10*hwconf.nr_of_pb
    byteTokenIn        = pktTokenIn # *(minLen+ifg_bytes)
    if min_token:
        byteTokenIn = max(byteTokenIn, min_token)

    tick = len(tick_freq)-1
    for i in range(len(tick_freq)):
        if pnb==1:
            #print " %s * %s = %s <= %s (=%s*%s)"% (tick_freq[i], pktTokenIn, tick_freq[i] * pktTokenIn, pktRate, fullPktRate, rate )
            if tick_freq[i] * pktTokenIn <= pktRate:
                tick = i
                break
        else:
            #print " %s * %s = %s <= %s (=%s*%s)"% (tick_freq[i], byteTokenIn, tick_freq[i] * byteTokenIn, byteRate, fullByteRate, rate )
            if tick_freq[i] * byteTokenIn <= byteRate:
                tick = i
                break

    while tick >= 0:
        pktTokenIn = int(1.0*pktRate   / tick_freq[tick])  
        byteTokenIn = int(1.0*byteRate / tick_freq[tick])

        print("######################################################")
        print("tbucket: fullByteRate: %s" % (fullByteRate))
        print("tbucket: byteRate: %s" % (byteRate))
        print("tbucket: tick: %s, tick freq: %s" % (tick, tick_freq[tick]))
        print("tbucket: byteTokenIn: %s" % (byteTokenIn))

        byteThr = byteTokenIn * 10
        if thr:
            byteThr = thr
        if min_thr:
            byteThr = max(min_thr, byteThr)
        pktThr = pktTokenIn * 10

        byteCap = byteThr + (byteTokenIn * 20)
        print("tbucket: byteCap: %s" % (byteCap))
        if cap:
            byteCap = cap
            print("tbucket: Overwriting byteCap: %s" % (byteCap))
        pktCap  = pktTokenIn * 20

        if pnb==1:
            if (pktTokenIn).bit_length() > constants['token_w'] or (pktCap).bit_length() > constants['bucket_w']:
                print("tick--", tick)
                tick-=1
                continue
        else:
            if (byteTokenIn).bit_length() > constants['token_w'] or (byteCap).bit_length() > constants['bucket_w']:
                print("tick--", tick, "(byteToken).bit_length() %s, token_w_w %s, (byteCap).bit_length() %s, bucket_w %s " % ((byteTokenIn).bit_length(), constants['token_w'], (byteCap).bit_length(), constants['bucket_w']))
                tick-=1
                continue
        break
    if tick < 0:
        assert False, "ERROR! Could not find a suitable tick. byte token w %s, pkt token w %s, byte cap w %s, pkt cap w %s" % ((byteTokenIn).bit_length(), (pktTokenIn).bit_length(), (byteCap).bit_length(), (pktCap).bit_length())
        
    #print "    token_buckets:" 
    #print "      fullByteRate", fullByteRate
    #print "      fullPktRate", fullPktRate
    #print "      byteRate", byteRate
    #print "      pktRate", pktRate
    #print "      pktTokenIn", pktTokenIn
    #print "      byteTokenIn", byteTokenIn
    #print "      tick", tick
    #print "      tick_freq", tick_freq[tick]
    #print "      rate",  rate
    #print "      pnb", pnb
    #print "      port_bw", port_bw 
    if pnb==1: 
        tok = pktTokenIn
        return rg_token_buckets(constants,
                                rate = 1.0*tick_freq[tick]*pktTokenIn/fullPktRate,
                                ifg  = ifg_bytes,
                                avb  = avb,
                                pnb  = 1,
                                tic  = tick,
                                tok  = pktTokenIn,
                                cap  = pktCap,
                                thr  = pktThr,
        )
    else:
        tok = byteTokenIn
        return rg_token_buckets(constants,
                                rate = 1.0*tick_freq[tick]*byteTokenIn/fullByteRate,
                                ifg = ifg_bytes,
                                avb  = avb,
                                pnb = 0,
                                tic = tick,
                                tok = byteTokenIn,
                                cap = byteCap,
                                thr = byteThr,
        )
def check_rate(data_sum,
               pkt_cnt,
               cycles,
               bw,
               max_pkt_bytes,
               bucket_reg,
               hwconf,
               t='port', # String decribing the index
               nr=None,
               ifg_bytes=24,
               scheduling_depth=1, # The number of packets that may be selected before, even though the shaper is permitting traffic
               gap_cycles = 0,
               avb = 0,
               tick = "default",
               granularity=None, # If other processes than ticks affect the granularity, for instance the transmission gates
):
    print()
    print("-----------")    
    if tick=="default" or tick=="core":
        tick_name = "Core"
        tick_freq = hwconf.tick_freq("core")
    elif tick=="ptp":
        tick_name = "PTP"
        tick_freq = hwconf.tick_freq("ptp")
    elif tick=="core_freq":
        tick_name = "core_freq"
        tick_freq = [hwconf.core_freq]
    elif type(tick) in (int, float):
        tick_freq = [tick]
        tick_name = "Custom"
    else:
        assert False
    #print "check_rate: tick_freq ", tick_freq
    
    ifg = ifg_bytes*8

    gap = gap_cycles if avb else 0     
    adj_cycles = cycles-gap
    if avb:
        print("check_rate %s AVB-mode with a gap of %s cycles" % (nr, gap))
    sim_pkt_rate = 1.0*hwconf.core_freq*(data_sum+(ifg*pkt_cnt))/(adj_cycles+1)
    
    if bucket_reg:
        pnb_str = 'byte'
        if bucket_reg.pnb:
            pnb_str = 'packet'
        expected_rate = bucket_reg.rate*bw
        try:
            miss_rate = abs(sim_pkt_rate-expected_rate)/expected_rate
        except:
            miss_rate = 1.0
        # Maximum error due to maximum packet
        pkts_ratio = 1.0*data_sum / (max_pkt_bytes * 8 * scheduling_depth) 
        # Maximum error due to tick
        ticks = 1.0*(adj_cycles + 1)/(hwconf.core_freq/tick_freq[bucket_reg.tic])
        if granularity:
            print("  ticks = %s / granularity %s = %s" % (ticks, granularity, ticks/granularity))
            ticks /= granularity
        # Error sum
        ratio = 1.0/(1.0/max(1, pkts_ratio) + 1.0/max(1, ticks))
        if ratio >= 4:
            max_miss = 3/ratio
        else:
            max_miss = 3
        print()
        print("  Shaped {5} rate on {8} {0} is {1}, expected {2} within a range of {3}.\n    Missed by {4}. Ticks {6}, maxLen bits {7}".format(
            nr,
            sim_pkt_rate,
            expected_rate,
            format(max_miss, '.2%'),
            format(miss_rate, '.2%'),
            pnb_str,
            ticks,
            max_pkt_bytes*8,
            t
        ))
        if ratio < 5:
            print("Warning: total number of ticks %s, or maxPkt/totalData %s gives too low ratio %s to measure the data rate with any reasonable accuracy on %s %s" %(ticks, pkts_ratio, ratio, t, nr))
            return None
        else:
            if miss_rate > max_miss:
                print("ERROR for %s %s" % (t, nr))
                return False
    else:
        print("%s %s: sim rate %s, no shaper configured" % (t, nr, sim_pkt_rate))
    return True
