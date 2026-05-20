from myhdl import always_comb, always, instances, Signal, intbv, concat
from .memory import memory
from .Common import (
    copySignal,
    pass_through,
    listType,
    compoundWidth,
    sync_flop,
    signalType,
)
from .hwconf import get_hwconf

hwconf = get_hwconf()


def clean_fifo_output(
    iempty, oempty, idata, odata, clk, rstn, ilevel=None, olevel=None
):
    gate = Signal(intbv(0)[1:])

    @always(clk.posedge, rstn.negedge)
    def ctrgate():
        if rstn == 0:
            gate.next = 0
        else:
            if iempty == 0:
                gate.next = 1

    @always_comb
    def gatefe():
        oempty.next = 1
        odata.next = 0
        if gate == 1:
            oempty.next = iempty
            odata.next = idata

    if ilevel is not None:

        @always_comb
        def gatelevel():
            olevel.next = 0
            if gate == 1:
                olevel.next = ilevel

    return instances()


def fifo_async(
    idata,
    odata,
    push,
    pop,
    full,
    almost_full,
    empty,
    almost_empty,
    level,
    iclk,
    oclk,
    irstn,
    orstn,
    depth,
    empty_margin="default",
    full_margin="default",
    consistency_check=None,
    memoryMode="mem",
    name="",
):
    if signalType(consistency_check):
        assert_ccheck = Signal(intbv(0)[1:0])

        @always(iclk.posedge, irstn.negedge)
        def ccheck():
            if irstn == 0:
                assert_ccheck.next = 0
            else:
                assert_ccheck.next = 0
                if consistency_check == 1:
                    "synthesis translate_off"
                    print("Consistency check", name)
                    "synthesis translate_on"
                    if empty == 0:
                        assert_ccheck.next = 1
                        "synthesis translate_off"
                        assert False, ("%s: Consistency check FAILED!" % name)
                        "synthesis translate_on"

    inst = []
    iflat = idata
    if listType(idata):
        iflat = Signal(intbv(0)[compoundWidth(idata) :])
        inst.append(pass_through(idata, iflat, name=name + ".flatten_in"))
    oflat = odata
    if listType(odata):
        oflat = Signal(intbv(0)[compoundWidth(odata) :])
        inst.append(pass_through(oflat, odata, name=name + ".flatten_out"))

    inst.append(
        fifo_async_signal(
            iflat,
            oflat,
            push,
            pop,
            full,
            almost_full,
            empty,
            almost_empty,
            level,
            iclk,
            oclk,
            irstn,
            orstn,
            depth,
            empty_margin,
            full_margin,
            memoryMode,
            name,
        )
    )
    return instances()


def fifo_async_signal(
    wdata,
    rdata,
    winc,
    rinc,
    wfull,
    almost_full,
    rempty,
    almost_empty,
    level,
    wclk,
    rclk,
    wrstn,
    rrstn,
    depth=4,
    empty_margin=1,
    full_margin=1,
    memoryMode="mem",
    name="",
):
    waddr = Signal(intbv(0, min=0, max=depth))
    asize = len(waddr)
    raddr = Signal(intbv(0)[asize:])
    wptr = Signal(intbv(0)[asize + 1 :])
    rptr = Signal(intbv(0)[asize + 1 :])
    wq2_rptr = Signal(intbv(0)[asize + 1 :])
    rq2_wptr = Signal(intbv(0)[asize + 1 :])
    empty_slot = copySignal(rq2_wptr)
    full_slot = copySignal(wq2_rptr)
    rempty_val = Signal(intbv(0)[1:])
    # empty_slot = copySignal(raddr)
    # full_slot  = copySignal(raddr)

    dirty_rdata = copySignal(rdata)
    mem_rdata = copySignal(rdata)
    hold_rdata = copySignal(rdata)
    did_read = Signal(intbv(0)[1:])
    re = Signal(intbv(0)[1:])
    dirty_rempty = copySignal(rempty)
    igate = clean_fifo_output(  # noqa: F841
        dirty_rempty, rempty, dirty_rdata, rdata, rclk, rrstn
    )

    if depth < 4:
        print("ERROR! Depth smaller than 4 is not supported for fifo", name)
        assert False
    if raddr.max != depth:
        print(
            "ERROR! Asynchronous FIFO depth", depth, "is not power of two in fifo", name
        )
        assert False
    if memoryMode == "mem":
        print(
            "fifo_async %s rclk %s, wclk %s, rrstn %s, wrstn %s"
            % (name, rclk, wclk, rrstn, wrstn),
            flush=1,
        )
        fifomem = memory(  # noqa: F841
            idata=wdata,
            odata=mem_rdata,
            raddr=raddr,
            waddr=waddr,
            renable=re,
            wenable=winc,
            wclk=wclk,
            clk=rclk,
            rstn=rrstn,
            wrstn=wrstn,
            depth=depth,
            name=name + ".mem",
        )

        @always(rclk.posedge, rrstn.negedge)
        def memrd():
            if rrstn == 0:
                did_read.next = 0
                hold_rdata.next = 0
            else:
                if did_read:
                    hold_rdata.next = mem_rdata
                did_read.next = re

        @always_comb
        def memre():
            re.next = int(
                rinc == 1 and rempty_val == 0 or dirty_rempty == 1 and rempty_val == 0
            )

        @always_comb
        def mux_rdata():
            if did_read:
                dirty_rdata.next = mem_rdata
            else:
                dirty_rdata.next = hold_rdata

    else:
        print("ERROR! Unsupported memoryMode", memoryMode, "for fifo", name)
        exit()

    # Comment out for now as some tests use much higer read clock
    # than write clock, which gives long overlaps.
    #
    # do_write = Signal(intbv(0)[1:])
    # do_read = Signal(intbv(0)[1:])
    # capt_waddr = copySignal(waddr)
    # capt_raddr = copySignal(raddr)
    #
    # @always(wclk.posedge, wrstn.negedge)
    # def check_capture_write():
    #     "synthesis translate_off"
    #     if wrstn == 0:
    #        do_write.next = 0
    #        capt_waddr.next = 0
    #     else:
    #         do_write.next = winc
    #         capt_waddr.next = waddr
    #     "synthesis translate_on"
    #
    # @always(rclk.posedge, rrstn.negedge)
    # def check_capture_read():
    #     "synthesis translate_off"
    #     if rrstn == 0:
    #        do_read.next = 0
    #        capt_raddr.next = 0
    #     else:
    #         do_read.next = not_rempty_val
    #         capt_raddr.next = raddr
    #     "synthesis translate_on"
    #
    # @always_comb
    # def check_rd_wr_conflict():
    #     "synthesis translate_off"
    #     if rrstn == 0:
    #         pass
    #     elif wrstn == 0:
    #         pass
    #     else:
    #          if (
    #              capt_raddr == capt_waddr
    #              and do_write == 1
    #              and do_read == 1
    #          ):
    #              print("ERROR! read and write to the same address")
    #              print("  raddr=%d  waddr=%d" % (capt_raddr, capt_waddr))
    #          "synthesis translate_on"

    sync_flop_depth = hwconf.sync_flop_depth
    sync_flop_mode = hwconf.sync_flop_mode

    if empty_margin == "default":
        empty_margin = sync_flop_depth - 1
    if full_margin == "default":
        full_margin = sync_flop_depth - 1

    if full_margin < sync_flop_depth - 1:
        print(
            "ERROR! %s Full margin %d is too small because the sync_flop_depth is %d"
            % (name, full_margin, sync_flop_depth)
        )
        assert False

    if empty_margin < sync_flop_depth - 1:
        print(
            "ERROR! %s Empty margin %d is too small because the sync_flop_depth is %d"
            % (name, empty_margin, sync_flop_depth)
        )
        assert False

    iSyncR2W = sync_flop(  # noqa: F841
        rptr,
        wq2_rptr,
        wclk,
        wrstn,
        depth=sync_flop_depth,
        itype=sync_flop_mode,
        name=name + ".syncR2W",
    )
    iSyncW2R = sync_flop(  # noqa: F841
        wptr,
        rq2_wptr,
        rclk,
        rrstn,
        depth=sync_flop_depth,
        itype=sync_flop_mode,
        name=name + ".syncW2R",
    )

    # inst_sync_r2w = sync_r2w(wq2_rptr,rptr,wclk,wrstn,name+".sync_r2w")
    # inst_sync_w2r = sync_w2r(rq2_wptr,wptr,rclk,rrstn,name+".sync_w2r")

    iRptrEmpty = rptr_empty(  # noqa: F841
        dirty_rempty,
        rempty_val,
        almost_empty,
        empty_slot,
        raddr,
        rptr,
        rq2_wptr,
        rinc,
        rclk,
        rrstn,
        empty_margin,
        name + ".empty",
    )
    iWptrFull = wptr_full(  # noqa: F841
        wfull,
        almost_full,
        full_slot,
        waddr,
        wptr,
        wq2_rptr,
        winc,
        wclk,
        wrstn,
        full_margin,
        name + ".full",
    )

    #    lm = level.max
    @always_comb
    def fifolevel():
        # if full_slot >= lm:
        #     "synthesis translate_off"
        #     print("%s ERROR! full_slot value %s out of range %s"
        #           %(name, full_slot, lm))
        #     assert False
        #     "synthesis translate_on"
        level.next = full_slot

    return instances()


def sync_r2w(wq2_rptr, rptr, wclk, wrstn, name=""):
    wq1_rptr = copySignal(wq2_rptr)

    @always(wclk.posedge, wrstn.negedge)
    def r2wlogic():
        if wrstn == 0:
            wq2_rptr.next = 0
            wq1_rptr.next = 0
        else:
            wq1_rptr.next = rptr
            wq2_rptr.next = wq1_rptr

    return instances()


def sync_w2r(rq2_wptr, wptr, rclk, rrstn, name=""):
    rq1_wptr = copySignal(rq2_wptr)

    @always(rclk.posedge, rrstn.negedge)
    def w2rlogic():
        if rrstn == 0:
            rq2_wptr.next = 0
            rq1_wptr.next = 0
        else:
            rq1_wptr.next = wptr
            rq2_wptr.next = rq1_wptr

    return instances()


def rptr_empty(
    rempty,
    rempty_val,
    almost_empty,
    empty_slot,
    raddr,
    rptr,
    rq2_wptr,
    rinc,
    rclk,
    rrstn,
    empty_margin=1,
    name="",
):
    addrsize = len(raddr)
    rbin = copySignal(rptr)
    rgraynext = copySignal(rptr)
    rbinnext = copySignal(rptr)
    alempty = copySignal(rempty_val)

    # -------------------
    # GRAYSTYLE2 pointer
    # -------------------
    @always(rclk.posedge, rrstn.negedge)
    def grayptr():
        if rrstn == 0:
            rbin.next = 0
            rptr.next = 0
        else:
            rbin.next = rbinnext
            rptr.next = rgraynext

    # Memory read-address pointer (okay to use binary to address memory)
    @always_comb
    def raddrptr():
        raddr.next = rbinnext[addrsize:]
        # raddr.next = rbin[addrsize:]

    @always_comb
    def nextbin():
        rbinnext.next = (rbin + (rinc & ~rempty)) & ((1 << (addrsize + 1)) - 1)

    @always_comb
    def nextgray():
        rgraynext.next = (rbinnext >> 1) ^ rbinnext

    rq2_wbin = copySignal(rq2_wptr)

    @always_comb
    def gray2bin():
        tmp = intbv(0)[addrsize + 1 :]
        for i in range(addrsize + 1):
            j = addrsize - i
            if j == addrsize:
                tmp[j] = rq2_wptr[j]
            else:
                tmp[j] = tmp[j + 1] ^ rq2_wptr[j]
        rq2_wbin.next = tmp

    @always(rclk.posedge, rrstn.negedge)
    def cmp():
        if rrstn == 0:
            empty_slot.next = 0
        else:
            if rq2_wbin < rbinnext:
                empty_slot.next = (rq2_wbin + (1 << (addrsize + 1)) - rbinnext) & (
                    (1 << (addrsize + 1)) - 1
                )
            else:
                empty_slot.next = rq2_wbin - rbinnext

    @always(rclk.posedge, rrstn.negedge)
    def alempty():
        if rrstn == 0:
            almost_empty.next = 1
        else:
            if empty_slot < empty_margin:
                almost_empty.next = 1
            else:
                almost_empty.next = 0

    # ---------------------------------------------------------------
    # FIFO empty when the next rptr == synchronized wptr or on reset
    # ---------------------------------------------------------------
    @always_comb
    def emptytest():
        rempty_val.next = rgraynext == rq2_wptr

    @always(rclk.posedge, rrstn.negedge)
    def setempty():
        if rrstn == 0:
            rempty.next = 1
        else:
            rempty.next = rempty_val

    return instances()


def wptr_full(
    wfull,
    almost_full,
    full_slot,
    waddr,
    wptr,
    wq2_rptr,
    winc,
    wclk,
    wrstn,
    full_margin=1,
    name="",
):
    wbin = copySignal(wptr)
    wgraynext = copySignal(wptr)
    wbinnext = copySignal(wptr)
    wfull_val = Signal(intbv(0)[1:])
    addrsize = len(waddr)
    depth = waddr.max

    wbinnextadd1 = copySignal(wbinnext)
    walfull_val = copySignal(wfull_val)
    walfull = copySignal(wfull)
    wgraynextadd1 = copySignal(wgraynext)

    # GRAYSTYLE2 pointer
    @always(wclk.posedge, wrstn.negedge)
    def grayptr():
        if wrstn == 0:
            wbin.next = 0
            wptr.next = 0
        else:
            wbin.next = wbinnext
            wptr.next = wgraynext

    # Memory write-address pointer (okay to use binary to address memory)
    @always_comb
    def waddrptr():
        waddr.next = wbin[addrsize:]

    @always_comb
    def nextbin():
        wbinnext.next = (wbin + (winc & ~wfull)) & (1 << (addrsize + 1)) - 1

    @always_comb
    def nextbinadd1():
        wbinnextadd1.next = (wbinnext + 1) & ((1 << (addrsize + 1)) - 1)

    @always_comb
    def nextgray():
        wgraynext.next = (wbinnext >> 1) ^ wbinnext
        wgraynextadd1.next = (wbinnextadd1 >> 1) ^ wbinnextadd1

    wq2_rbin = copySignal(wq2_rptr)

    @always_comb
    def gray2bin():
        tmp = intbv(0)[addrsize + 1 :]
        for i in range(addrsize + 1):
            j = addrsize - i
            if j == addrsize:
                tmp[j] = wq2_rptr[j]
            else:
                tmp[j] = tmp[j + 1] ^ wq2_rptr[j]
        wq2_rbin.next = tmp

    @always_comb
    def cmp():
        if wq2_rbin > wbinnext:
            full_slot.next = (wbinnext + (1 << (addrsize + 1)) - wq2_rbin) & (
                (1 << (addrsize + 1)) - 1
            )
        else:
            full_slot.next = wbinnext - wq2_rbin

    @always(wclk.posedge, wrstn.negedge)
    def alfull():
        if wrstn == 0:
            almost_full.next = 0
        else:
            if full_slot > depth - full_margin - 1:
                almost_full.next = 1
            else:
                almost_full.next = 0
            "synthesis translate_off"
            if winc == 1 and wfull == 1:
                print("ERROR! Write to full FIFO")
                assert False
            "synthesis translate_on"

    # ------------------------------------------------------------------
    # Simplified version of the three necessary full-tests:
    # assign wfull_val=((wgnext[ADDRSIZE]
    # !=wq2_rptr[ADDRSIZE] ) &&
    #
    # (wgnext[ADDRSIZE-1] !=wq2_rptr[ADDRSIZE-1]) &&
    #
    # (wgnext[ADDRSIZE-2:0]==wq2_rptr[ADDRSIZE-2:0]));
    # ------------------------------------------------------------------
    @always_comb
    def fulltest():
        wfull_val.next = wgraynext == concat(
            ~wq2_rptr[addrsize + 1 : addrsize - 1], wq2_rptr[addrsize - 1 : 0]
        )
        walfull_val.next = wgraynextadd1 == concat(
            ~wq2_rptr[addrsize + 1 : addrsize - 1], wq2_rptr[addrsize - 1 : 0]
        )

    @always(wclk.posedge, wrstn.negedge)
    def setfull():
        if wrstn == 0:
            wfull.next = 0
            walfull.next = 0
        else:
            wfull.next = wfull_val
            walfull.next = walfull_val

    # @always_comb
    # def alfull():
    #     if wfull==1 or walfull==1:
    #         almost_full.next = 1
    #     else:
    #         almost_full.next = 0

    return instances()
