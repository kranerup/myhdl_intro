"""
TCAM wrapping module
"""

from myhdl import module, instances, always, always_comb, Struct, inline, ConcatSignal
from modules.conf.confif import ConfIf, ACCUMULATOR, NONE, ROK, WOK
from modules.conf.conf_rq_fifo import conf_rq_fifo
from modules.common.signal import signal, sigarray
from modules.common.hwconf import get_hwconf
from modules.common.memory_cam import memory_cam
from modules.verilog.tcam.es.es_tcam import es_tcam


# @module
def tcam_bus(
    clk,
    rstn,
    confbus,
    settings,
    cam_search,
    cam_key,
    cam_answer,
    cam_mask,
    key_mask,
    input_flops,
    output_flops,
    name="",
):
    hwconf = get_hwconf()
    depth = settings.depth()
    start_addr = settings.start_address
    end_addr = settings.end_address
    offset_bits = (end_addr - start_addr).bit_length()
    index_bits = (depth - 1).bit_length()
    latency = input_flops + output_flops + 1
    cdbits = len(confbus.request.data)
    cdmask = (1 << cdbits) - 1
    nid = hwconf.nr_of_id

    if key_mask:
        kbits = len(cam_key) // 2
    else:
        kbits = len(cam_key)
    if cam_mask:
        dbits = 2 * kbits + 1
    else:
        dbits = kbits + 1
    dwords = (dbits + cdbits - 1) // cdbits
    entry_size = (end_addr - start_addr) // depth

    offset = signal(offset_bits)
    idx = signal(index_bits)
    if dwords > 1:
        word_idx = signal((dwords - 1).bit_length())
        rwidxes = sigarray(len(word_idx), nid)
    else:
        word_idx = 0
        rwidxes = sigarray(1, nid)
    conf_hit = signal()
    rstatus = sigarray(len(confbus.reply.status), nid)

    class Pending(Struct):
        def __init__(self):
            self.active = signal()
            self.write = signal()
            self.id = signal(len(confbus.request.id))
            self.idx = signal(index_bits)
            self.data = sigarray(cdbits, dwords)
            self.done = signal()

    pend = Pending()

    wdata_c = ConcatSignal(*reversed(pend.data)) if dwords > 1 else pend.data[0]
    wdata = signal(dbits)
    rdata = signal(dbits)

    @always_comb
    def assign_wdata():
        wdata.next = wdata_c[dbits:0]

    @inline
    def reset_pending(s):
        s.active.next = 0
        s.write.next = 0
        s.id.next = 0
        s.idx.next = 0
        for i in range(dwords):
            s.data[i].next = 0

    lconf = ConfIf(len(confbus.request.data), offset_bits, len(confbus.request.id))

    has_ids = hwconf.nr_of_id > 1 or None
    pop = signal() if has_ids else None

    crq = conf_rq_fifo(  # noqa: F841
        clk=has_ids and clk,
        rstn=has_ids and rstn,
        conf_in=confbus,
        conf_out=lconf,
        pop=pop,
        start_address=start_addr,
        end_address=end_addr,
    )

    @always_comb
    def calc_index():
        offset.next = lconf.request.address
        idx.next = offset // entry_size
        if dwords > 1:
            word_idx.next = offset - idx * entry_size
        conf_hit.next = lconf.request.re | lconf.request.we

    @always_comb
    def reply():
        lconf.reply.status.next = NONE
        lconf.reply.data.next = 0
        lconf.reply.id.next = 0
        for i in range(nid):
            if rstatus[i] != NONE:
                lconf.reply.id.next = i
                lconf.reply.status.next = rstatus[i]
                if rstatus[i] == ROK:
                    lconf.reply.data.next = pend.data[rwidxes[i]]

    @always(clk.posedge, rstn.negedge)
    def addr_decode():
        if rstn == 0:
            reset_pending(pend)
            for i in range(nid):
                rstatus[i].next = NONE
                rwidxes[i].next = 0
        else:
            if conf_hit & ~pend.active:
                if lconf.request.we:
                    pend.data[word_idx].next = lconf.request.data
                    if lconf.request.type == ACCUMULATOR:
                        rstatus[lconf.request.id].next = WOK
                    else:
                        pend.active.next = 1
                        pend.write.next = 1
                        pend.id.next = lconf.request.id
                        pend.idx.next = idx
                else:
                    rwidxes[lconf.request.id].next = word_idx
                    if lconf.request.type == ACCUMULATOR:
                        rstatus[lconf.request.id].next = ROK
                    else:
                        pend.active.next = 1
                        pend.write.next = 0
                        pend.id.next = lconf.request.id
                        pend.idx.next = idx

            if lconf.reply.status != NONE:
                rstatus[lconf.reply.id].next = NONE

            if pend.done:
                if pend.write:
                    rstatus[pend.id].next = WOK
                else:
                    for i in range(dwords):
                        pend.data[i].next = (rdata >> (i * cdbits)) & cdmask
                    rstatus[pend.id].next = ROK
                pend.active.next = 0

    if has_ids:

        @always_comb
        def conf_pop():
            pop.next = conf_hit & ~pend.active

    if hwconf.cam_model in ("default", "default_rmask", "cavium"):
        lat_bits = latency.bit_length()

        renable = signal()
        wenable = signal()
        if latency > 1:
            doing_read = signal(lat_bits)
            doing_write = signal(lat_bits)
        else:
            doing_read = 0
            doing_write = 0

        @always_comb
        def start_op():
            renable.next = int(
                pend.active == 1
                and pend.write == 0
                and pend.done == 0
                and doing_read == 0
                and cam_search == 0
            )
            wenable.next = int(
                pend.active == 1
                and pend.write == 1
                and pend.done == 0
                and doing_write == 0
                and cam_search == 0
            )

        @inline
        def handle_rw(en, doing, s, lat):
            if en:
                if lat <= 1:
                    s.done.next = 1
                else:
                    doing.next = lat - 1
            if lat > 1:
                if doing != 0:
                    doing.next = doing - 1
                    if doing == 1:
                        s.done.next = 1

        @always(clk.posedge, rstn.negedge)
        def rw_state():
            if rstn == 0:
                pend.done.next = 0
                if latency > 1:
                    doing_read.next = 0
                    doing_write.next = 0
            else:
                pend.done.next = 0
                handle_rw(renable, doing_read, pend, latency)
                handle_rw(wenable, doing_write, pend, latency)

        cam = memory_cam(  # noqa: F841
            clk=clk,
            rstn=rstn,
            cam_search=cam_search,
            cam_key=cam_key,
            cam_answer=cam_answer,
            cam_mask=cam_mask,
            key_mask=key_mask,
            idata=wdata,
            odata=rdata,
            raddr=pend.idx,
            waddr=pend.idx,
            renable=renable,
            wenable=wenable,
            depth=depth,
            input_flops=input_flops,
            output_flops=output_flops,
            name=f"{name}.cam",
        )

    elif hwconf.cam_model == "es":
        cam = es_tcam(  # noqa: F841
            clk=clk,
            rstn=rstn,
            cam_search=cam_search,
            cam_key=cam_key,
            cam_answer=cam_answer,
            cam_mask=cam_mask,
            key_mask=key_mask,
            wdata=wdata,
            rdata=rdata,
            write=pend.write,
            addr=pend.idx,
            active=pend.active,
            done=pend.done,
            depth=depth,
            latency=input_flops + output_flops + 1,
            name=f"{name}.cam",
        )

    else:
        assert False, f"Unkonwn hwconf.cam_model: {hwconf.cam_model}"

    return instances()


def tcam(
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
    settings,
    cam_search,
    cam_key,
    cam_answer,
    cam_mask,
    key_mask,
    input_flops,
    output_flops,
    name="",
):
    confbus = ConfIf(len(request_data), len(request_address), len(request_id))

    @always_comb
    def assign_request():
        confbus.request.address.next = request_address
        confbus.request.data.next = request_data
        confbus.request.id.next = request_id
        confbus.request.type.next = request_type
        confbus.request.re.next = request_re
        confbus.request.we.next = request_we

    @always_comb
    def assign_reply():
        reply_data.next = confbus.reply.data
        reply_id.next = confbus.reply.id
        reply_status.next = confbus.reply.status

    tc = tcam_bus(  # noqa: F841
        clk=clk,
        rstn=rstn,
        confbus=confbus,
        settings=settings,
        cam_search=cam_search,
        cam_key=cam_key,
        cam_answer=cam_answer,
        cam_mask=cam_mask,
        key_mask=key_mask,
        input_flops=input_flops,
        output_flops=output_flops,
        name=name,
    )

    return instances()
