import unittest
from myhdl import (
    intbv, Signal, instances, instance, delay, always, StopSimulation,
)
from unittesting.ClockedTestCase import ClockedTestCase
from .Common import value, listType, compoundWidth, multiflop, copySignal
from modules.common.Common import clock_divider
from .memory import memory, memory_init
from .memory_overclock_wide import memory_overclock_wide
from .memory_overclock_ports import memory_overclock_ports
from .memory_overclock_merge import memory_overclock_merge
from .memory_multi_access import memory_multi_access
from .memory_latency import memory_latency
from random import randrange
import random


def _mask_data(data, mask, old_data):
    dbits = len(data)
    mbits = len(mask)
    bpm = dbits // mbits
    d = int(data)
    od = int(old_data)
    m = int(mask)
    v = 0
    bm = (1 << bpm) - 1
    for i in range(mbits):
        dd = d if ((m >> i) & 1) else od
        v |= dd & (bm << (i * bpm))
    return v


class UnitTest(unittest.TestCase, ClockedTestCase):
    def setUp(self):
        super(UnitTest, self).setUpSeed()

    def test_memory(self):
        self.run_test_memory(init=False)

    def test_memory_short(self):
        self.run_test_memory(init=False, duration="short")

    def test_memory_long(self):
        self.run_test_memory(init=False, duration="long", lmode=False)

    def test_memory_tsmc(self):
        self.run_test_memory(mode="tsmc", duration="long", lmode=False)

    def test_memory_vm(self):
        self.run_test_memory(mode="vm", duration="default", lmode=False)
    def test_memory_vm_short(self):
        self.run_test_memory(mode="vm_short", duration="default", lmode=False)

    def test_memory_init(self):
        self.run_test_memory(
            init=True,
        )

    def test_memory_async(self):
        self.run_test_memory(init=False, is_async=True)

    def test_memory_async_vm(self):
        self.run_test_memory(init=False, is_async=True, mode="vm")

    def test_memory_wide(self):
        self.run_test_memory(wide=True, lmode=False)

    def test_memory_wide_short(self):
        self.run_test_memory(wide=True, lmode=False, duration="short")

    def test_memory_wide_init(self):
        self.run_test_memory(wide=True, init=True, lmode=False)

    def test_memory_merge(self):
        self.run_test_memory(merge=True, lmode=False)

    def test_memory_merge_short(self):
        self.run_test_memory(merge=True, lmode=False, duration="short")

    def test_memory_merge_init(self):
        self.run_test_memory(merge=True, init=True, lmode=False)

    def test_memory_ports(self):
        self.run_test_memory(mport=True, lmode=False)

    def test_memory_ports_short(self):
        self.run_test_memory(mport=True, lmode=False, duration="short")

    def test_memory_ports_init(self):
        self.run_test_memory(mport=True, init=True, lmode=False)

    def test_memory_multi(self):
        self.run_test_memory(multi=True, lmode=False)

    def test_memory_multi_short(self):
        self.run_test_memory(multi=True, lmode=False, duration="short")

    def test_memory_custom(self):
        self.run_test_memory(mode="custom", duration="default", lmode=False)
        
    def run_test_memory(
        self,
        init=False,
        is_async=False,
        wide=False,
        mport=False,
        merge=False,
        multi=False,
        mode="inferred",
        duration="default",
        lmode=True,
    ):
        # The testbench needs to have the parameters cosim and synt,
        # and they have to be set as false by default
        # It needs to be named tb_{blockName}
        def testbench(
            modName,
            blockName,
            postfix,
            width,
            depth,
            reset_value=27,
            write_through=0,
            pre_load=0,
            is_async=False,
            divisor=0,
            inst=1,
            hwc=None,
            ports=2,
            multi=False,
            input_flops=0,
            output_flops=0,
            force_latency=None,
            nr=1000,
            wmask=None,
            cosim=False,
            synt=False,
        ):
            print(
                "Running",
                modName,
                blockName,
                postfix,
                "w",
                width,
                "s",
                depth,
                "reset",
                reset_value,
                "wt",
                write_through,
                "pl",
                pre_load,
                "is_async",
                is_async,
                "divisor",
                divisor,
                "inst",
                inst,
                "ports",
                ports,
                "input_flops",
                input_flops,
                "output_flops",
                output_flops,
                "nr",
                nr,
                cosim,
                synt,
                wmask,
            )
            rclk = Signal(intbv(0)[1:0])
            wclk = Signal(intbv(0)[1:0])
            rrstn = Signal(intbv(0)[1:0])
            wrstn = Signal(intbv(0)[1:0])
            if wmask:
                w = wmask
                wmask = Signal(intbv((1 << w)-1)[w:])
                last_wmask = Signal(intbv((1 << w)-1)[w:])
                has_wmask = True
            else:
                has_wmask = False

            verbose = False

            listMode = False
            if listType(width):
                listMode = True

            @instance
            def rrstngen():
                rrstn.next = 0
                yield delay(100)
                yield rclk.posedge
                rrstn.next = 1

            @instance
            def wrstngen():
                wrstn.next = 0
                yield delay(101)
                yield wclk.posedge
                wrstn.next = 1

            if merge:
                print("Merge-mode")
                mems = inst
                prts = inst
            elif mport:
                print("Mport-mode")
                mems = 1
                prts = ports
            elif multi:
                print("Multi-access-mode")
                mems = 1
                prts = ports
            else:
                print("Vanilla-mode")
                mems = 1
                prts = 1

            if divisor > 0:
                master_clk = Signal(intbv(0)[1:0])
                mclk = Signal(intbv(0)[1:0])

                @always(delay(10))
                def clkgen():
                    master_clk.next = not master_clk

                iDivc = clock_divider(
                    master_clk=master_clk,
                    divisor=divisor * 2,
                    clk=rclk,
                    rstn=rrstn,
                    name="iDivc",
                )
                iDivm = clock_divider(
                    master_clk=master_clk, divisor=2, clk=mclk, rstn=rrstn, name="iDivm"
                )
            else:
                mclk = rclk

                @always(delay(10))
                def rclkgen():
                    rclk.next = not rclk

                # TODO: Actually asyncronous clocks
                @always(delay(10))
                def wclkgen():
                    wclk.next = not wclk

            if listType(width):
                idata = [Signal(intbv(0)[x:]) for x in width]
                last_idata = [Signal(intbv(0)[x:]) for x in width]
                odata = [Signal(intbv(0)[x:]) for x in width]
            else:
                idata = Signal(intbv(0)[width:])
                last_idata = Signal(intbv(0)[width:])
                odata = Signal(intbv(0)[width:])
            print("Prts:", prts)
            if prts > 1:
                raddr = [Signal(intbv(0, min=0, max=depth)) for _ in range(prts)]
                waddr = [Signal(intbv(0, min=0, max=depth)) for _ in range(prts)]
                renable = [Signal(intbv(0)[1:0]) for _ in range(prts)]
                wenable = [Signal(intbv(0)[1:0]) for _ in range(prts)]
            else:
                raddr = Signal(intbv(0, min=0, max=depth))
                waddr = Signal(intbv(0, min=0, max=depth))
                renable = Signal(intbv(0)[1:0])
                wenable = Signal(intbv(0)[1:0])

            # Generate the data
            def dataGenerator(index=0):
                if listMode:
                    return randrange(2 ** len(idata[index]))
                else:
                    return randrange(2 ** len(idata))

            soft_reset = None
            doing_init = None
            consistency_data = None  # [ Signal(intbv(0)[compoundWidth(idata):]) for _ in range(depth) ]
            single_ported = False
            if ports == 1:
                single_ported = True
            if init == True:
                soft_reset = Signal(intbv(0)[1:])
                doing_init = Signal(intbv(0)[1:])

            print(
                "init==%s and wide==%s and ports==%s, mport==%s, inst==%s"
                % (init, wide, ports, mport, inst)
            )
            if init and not wide and inst == 1 and not mport:
                print("Creating memory_init dut")
                module = memory_init
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i o i i o v v v v v v v v v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    soft_reset,
                    doing_init,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                )
            elif is_async:
                module = memory
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o v v v v v v v v v i i i v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                    wclk,
                    wrstn,
                    wmask,
                    False,
                )
            elif wide:
                print("Creating memory_overclock_wide dut")
                module = memory_overclock_wide
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o v v v v v v sv v v i i i v i o v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                    None,
                    None,
                    mclk,
                    divisor,
                    soft_reset,
                    doing_init,
                    force_latency,
                )
            elif inst > 1:
                print("Creating memory_overclock_merge dut")
                module = memory_overclock_merge
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o v v v v v v sv v v i i i v i o v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                    None,
                    None,
                    mclk,
                    divisor,
                    soft_reset,
                    doing_init,
                    force_latency,
                )
            elif mport:
                print("Creating memory_overclock_ports dut")
                module = memory_overclock_ports
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o v v v v v v sv v v i i i v i o v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                    None,
                    None,
                    mclk,
                    divisor,
                    soft_reset,
                    doing_init,
                    force_latency,
                )
            elif multi:
                print("Creating memory_multi_access dut")
                imask = None
                mode = "ff"
                module = memory_multi_access
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o i v v v v v v sv v v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    imask,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    mode,
                )
            else:
                module = memory
                dut = self.createDUT(
                    modName,
                    blockName,
                    postfix,
                    cosim,
                    synt,
                    "i o i i i i i i o v v v v v v v v v i i i v".split(),
                    module,
                    idata,
                    odata,
                    raddr,
                    waddr,
                    renable,
                    wenable,
                    rclk,
                    rrstn,
                    consistency_data,
                    depth,
                    write_through,
                    reset_value,
                    pre_load,
                    conf_load,
                    input_flops,
                    output_flops,
                    hwc,
                    single_ported,
                    None,
                    None,
                    wmask,
                    False,
                )


            rlat = memory_latency(
                input_flops, output_flops, divisor, wide, mport, merge
            )
            if force_latency != None:
                rlat = force_latency

            if inst == 1 and not mport and not multi:
                print("Single and dual port mode")
                #################################################3
                # Single and dual port mode
                #
                if pre_load:
                    rval = reset_value
                else:
                    rval = 0
                scoreboard = [
                    Signal(intbv(0)[compoundWidth(idata) :]) for x in range(depth)
                ]
                written = Signal(intbv(0)[depth:])

                readCnt = Signal(intbv(0)[64:])

                last_ra = Signal(intbv(0)[len(raddr) :])
                last_re = Signal(intbv(0)[1:0])
                last_wa = Signal(intbv(0)[len(waddr) :])
                last_we = Signal(intbv(0)[1:0])


                @instance
                def addr_gen():
                    yield rclk.posedge
                    wenable.next = False
                    if has_wmask:
                        wmask.next = 0
                    while not rrstn:
                        yield rclk.posedge
                    yield rclk.posedge
                    yield rclk.posedge
                    yield rclk.posedge
                    if doing_init == 1:
                        if verbose:
                            print("Waiting for init...")
                    initcnt = 0
                    for i in range(depth):
                        scoreboard[i].next = rval
                    while doing_init == 1:
                        yield rclk.posedge
                        initcnt = initcnt + 1
                    if initcnt > 0:
                        if verbose:
                            print("... done in", initcnt, "clock cycles")
                    while True:
                        write = randrange(100) < 95
                        read = randrange(100) < 95
                        if single_ported and write:
                            read = False
                        # Two random addresses (unique if write_through=0)
                        wa = randrange(0, depth)
                        ra = randrange(0, depth)
                        if read == 1 and write == 1 and write_through == 0:
                            if depth == 1:
                                read = write == 0
                            else:
                                while ra == wa:
                                    ra = randrange(0, depth)
                        # Write
                        if listMode:
                            val = [
                                randrange(2 ** (len(idata[x])))
                                for x in range(len(idata))
                            ]
                            for m in range(len(idata)):
                                idata[m].next = val[m]
                        else:
                            val = randrange(2 ** (len(idata)))
                            idata.next = val
                        wenable.next = write
                        if has_wmask:
                            wmask.next = randrange(2 ** len(wmask))
                        waddr.next = wa

                        # Read
                        renable.next = read
                        raddr.next = ra
                        yield rclk.posedge
                        yield delay(1)
                        if last_we:
                            v = value(last_idata)
                            if has_wmask:
                                v = _mask_data(
                                    last_idata, last_wmask, scoreboard[last_wa]
                                )
                            scoreboard[last_wa].next = v
                            written.next[last_wa] = 1
                        if readCnt % 1000 == 0:
                            if verbose:
                                print("readCnt:", readCnt)
                        if readCnt >= nr:
                            yield rclk.posedge
                            raise StopSimulation

                zFlopre = multiflop(
                    renable, last_re, depth=rlat, clk=rclk, rstn=rrstn, name="fre"
                )
                zFlopra = multiflop(
                    raddr, last_ra, depth=rlat, clk=rclk, rstn=rrstn, name="fra"
                )
                zFlopwe = multiflop(
                    wenable, last_we, depth=rlat, clk=rclk, rstn=rrstn, name="fwe"
                )
                zFlopwa = multiflop(
                    waddr, last_wa, depth=rlat, clk=rclk, rstn=rrstn, name="fwa"
                )
                zFlopid = multiflop(
                    idata, last_idata, depth=rlat, clk=rclk, rstn=rrstn, name="fwd"
                )
                if has_wmask:
                    zFlopwm = multiflop(
                        wmask, last_wmask, depth=rlat, clk=rclk, rstn=rrstn, name="fwm"
                    )

                @always(rclk.posedge)
                def compare():
                    if rrstn == 0:
                        readCnt.next = 0
                    else:
                        if (
                            last_re
                            and rrstn
                            and (doing_init == 0 or doing_init == None)
                        ):
                            if last_we and last_wa == last_ra:
                                if write_through == 0:
                                    print(
                                        "ERROR! Write through for a non-write-through memory at address",
                                        hex(last_wa),
                                    )
                                    assert False
                                else:
                                    if value(last_idata) != value(odata):
                                        print(
                                            "ERROR! Write through failed. idata %s != odata %s"
                                            % (
                                                hex(value(last_idata)),
                                                hex(value(odata)),
                                            )
                                        )
                                        assert False
                            elif written[last_ra] == 1:
                                readCnt.next += 1
                                # print "addr", last_ra, scoreboard[last_ra], value(odata)
                                if scoreboard[last_ra] != value(odata):
                                    print(
                                        "ERROR! scoreboard[%s] = %s != odata %s"
                                        % (
                                            hex(last_ra),
                                            hex(scoreboard[last_ra]),
                                            hex(value(odata)),
                                        )
                                    )
                                    assert False
                                else:
                                    if verbose:
                                        print(
                                            "OK scoreboard[%s] = %s == odata %s"
                                            % (
                                                hex(last_ra),
                                                hex(scoreboard[last_ra]),
                                                hex(value(odata)),
                                            )
                                        )
                            elif init == True:
                                if reset_value != value(odata):
                                    print(
                                        "ERROR! reset_value = %s != odata %s"
                                        % (hex(reset_value), hex(value(odata)))
                                    )
                                    assert False
                            else:
                                if verbose:
                                    print(
                                        "OK %s not written (produced %s)"
                                        % (hex(last_ra), hex(value(odata)))
                                    )

            else:
                print("Multiport and merge mode")
                #################################################3
                # Multiport and merge mode
                #

                scoreboard = [
                    [copySignal(idata[i]) for x in range(depth)] for i in range(mems)
                ]
                written = [Signal(intbv(0)[depth:]) for _ in range(mems)]

                readCnt = [Signal(intbv(0)) for _ in range(mems)]
                last_ra = [Signal(intbv(0)[len(raddr[i]) :]) for i in range(prts)]
                last_re = [Signal(intbv(0)[1:0]) for _ in range(prts)]
                last_wa = [Signal(intbv(0)[len(waddr[i]) :]) for i in range(prts)]
                last_we = [Signal(intbv(0)[1:0]) for _ in range(prts)]
                # last_idata = [ copySignal(idata[i])    for i in range(prts) ]

                zFlopre2 = multiflop(
                    renable, last_re, depth=rlat, clk=rclk, rstn=rrstn, name="fre2"
                )
                zFlopra2 = multiflop(
                    raddr, last_ra, depth=rlat, clk=rclk, rstn=rrstn, name="fra2"
                )
                zFlopwe2 = multiflop(
                    wenable, last_we, depth=rlat, clk=rclk, rstn=rrstn, name="fwe2"
                )
                zFlopwa2 = multiflop(
                    waddr, last_wa, depth=rlat, clk=rclk, rstn=rrstn, name="fwa2"
                )
                zFlopid2 = multiflop(
                    idata, last_idata, depth=rlat, clk=rclk, rstn=rrstn, name="fwd2"
                )

                @instance
                def addr_gen():
                    yield rclk.posedge
                    for i in range(prts):
                        wenable[i].next = 0
                    while not rrstn:
                        yield rclk.posedge
                    yield rclk.posedge
                    yield rclk.posedge
                    yield rclk.posedge
                    if doing_init == 1:
                        if verbose:
                            print("Waiting for init...")
                    initcnt = 0
                    while doing_init == 1:
                        yield rclk.posedge
                        initcnt = initcnt + 1
                    if initcnt > 0:
                        if verbose:
                            print("... done in", initcnt, "clock cycles")
                    while True:
                        write = []
                        wa = []
                        read = []
                        ra = []
                        val = []
                        for i in range(prts):
                            write.append(randrange(3) == 0)
                            wa.append(randrange(0, depth))
                            val.append(randrange(2 ** (len(idata[i]))))
                        for i in range(prts):
                            read.append(randrange(2) == 0)
                            if single_ported and write[i]:
                                read[i] = False
                            # Two random addresses (unique if write_through=0)
                            ra.append(randrange(0, depth))
                        for i in range(prts):
                            if mport or multi:
                                # In multi-port mode just skip the read when there is a collision with any write
                                for j in range(prts):
                                    if (
                                        read[i] == 1
                                        and 1 in write
                                        and write_through == 0
                                    ):
                                        if depth == 1:
                                            read[i] = write[j] == 0
                                        else:
                                            if ra[i] == wa[j] and write[j]:
                                                read[i] = 0
                            else:
                                if read[i] == 1 and write[i] and write_through == 0:
                                    if depth == 1:
                                        read[i] = write[i] == 0
                                    else:
                                        while ra[i] == wa[i]:
                                            ra[i] = randrange(depth)

                            # Write
                            idata[i].next = val[i]
                            wenable[i].next = write[i]
                            waddr[i].next = wa[i]

                            # Read
                            renable[i].next = read[i]
                            raddr[i].next = ra[i]
                        yield rclk.posedge
                        yield delay(1)
                        for i in range(prts):
                            idx = i if merge else 0
                            if last_we[i]:
                                scoreboard[idx][last_wa[i]].next = value(last_idata[i])
                                written[idx].next[last_wa[i]] = 1
                            if min(readCnt) >= nr:
                                yield rclk.posedge
                                raise StopSimulation

                @always(rclk.posedge)
                def compare():
                    if rrstn == 0:
                        for i in range(mems):
                            readCnt[i].next = 0
                    else:
                        for i in range(prts):
                            idx = i if merge else 0
                            if (
                                last_re[i]
                                and rrstn
                                and (doing_init == 0 or doing_init == None)
                            ):
                                hitwe = 0
                                hitid = 0
                                if (multi or mport) and write_through:
                                    for j in range(prts):
                                        if last_we[j] and last_wa[j] == last_ra[i]:
                                            hitid = j
                                            hitwe = 1
                                if hitwe:
                                    if value(odata[i]) != value(last_idata[hitid]):
                                        print(
                                            "ERROR! Write through data mismatch exp %s (idata from port %s), got %s for port %s addr %s"
                                            % (
                                                hex(last_idata[j]),
                                                hitid,
                                                hex(odata[i]),
                                                i,
                                                hex(last_ra[i]),
                                            )
                                        )
                                        assert False

                                elif last_we[i] and last_wa[i] == last_ra[i]:
                                    if write_through == 0:
                                        print(
                                            "ERROR! Write through for a non-write-through memory at address",
                                            hex(last_wa),
                                        )
                                        assert False
                                    elif value(last_idata[i]) != value(odata[i]):
                                        print(
                                            "ERROR! Write through data mismatch exp %s, got %s for port %s addr %s"
                                            % (
                                                hex(last_idata[i]),
                                                hex(odata[i]),
                                                i,
                                                hex(last_ra[i]),
                                            )
                                        )
                                        assert False
                                elif written[idx][last_ra[i]] == 1:
                                    readCnt[idx].next += 1
                                    if scoreboard[idx][last_ra[i]] != value(odata[i]):
                                        print(
                                            "ERROR! Write data mismatch exp %s, got %s for port %s address %s"
                                            % (
                                                hex(scoreboard[idx][last_ra[i]]),
                                                hex(odata[i]),
                                                i,
                                                hex(last_ra[i]),
                                            )
                                        )
                                        assert False
                                elif init == True:
                                    if reset_value != value(odata[i]):
                                        print(
                                            "ERROR! Reset value mismatch exp %s, got %s for port %s addr %s"
                                            % (
                                                hex(reset_value),
                                                hex(odata[i]),
                                                i,
                                                hex(last_ra[i]),
                                            )
                                        )
                                        assert False

            return instances()

        class Hwc(object):
            def __init__(
                self,
                dft = 0,
                memory_flop_limit=None,
                technology="asic",
                memory_mode="inferred",
                memory_target="all",
                memory_ecc_min_size=None,    
                evaluation_timeout_cnt=None,
                force_flopmem = [],
                allow_2c_flopmem = False,
                memory_ecc_list = [],
                memory_max_width=None,
                memory_max_depth=None,
                memory_force_input_flop=0,
                memory_force_output_flop=0,
                memory_force_in_or_out_flop=0,
            ):
                self.dft = dft
                self.memory_flop_limit = memory_flop_limit
                self.memory_flop_dlimit = None
                self.technology = technology
                self.memory_mode = memory_mode
                self.memory_target = memory_target
                self.memory_ecc_min_size = memory_ecc_min_size
                self.evaluation_timeout_cnt = evaluation_timeout_cnt
                self.force_flopmem = force_flopmem
                self.allow_2c_flopmem = allow_2c_flopmem,
                self.memory_ecc_list = memory_ecc_list
                self.memory_max_width = memory_max_width
                self.memory_max_depth = memory_max_depth
                self.memory_connect_unused_rstn = 0
                self.memory_force_input_flop = memory_force_input_flop
                self.memory_force_output_flop = memory_force_output_flop
                self.memory_force_in_or_out_flop = memory_force_in_or_out_flop

        memory_ports = [2]
        memory_insts = [1]
        memory_iflops = [0, 1]
        memory_oflops = [0, 1]
        memory_wt = [0, 1]
        divisors = [0]
        force_latencies = [None]
        wmask = [None]

        min_signal_width = 1
        min_depth = 1

        if duration == "short":
            number_of_configurations = 1
            max_list_width = 2
            max_signal_width_in_list = 7
            max_signal_width = 34
            max_depth = 10
            dmult = 100
        elif duration == "default":
            number_of_configurations = 100
            max_list_width = 13
            max_signal_width_in_list = 18
            max_signal_width = 128
            max_depth = 128
            dmult = 256
        elif duration == "long":
            number_of_configurations = 1
            max_list_width = 200
            max_signal_width_in_list = 66
            max_signal_width = 2048
            max_depth = 33000
            dmult = 0.5
        else:
            assert False, "Unknown duration %s" % duration

        technologies = ['asic']
        if mode == "inferred":
            memory_modes = ["inferred"]
            memory_flop_limits = [None]
            memory_max_widths = [None]
            memory_max_depths = [None]
        elif mode == "vm":
            if is_async:
                memory_ports = [2]
            else:
                memory_ports = [1, 2]
            technologies = ['asic', 'fpga']
            memory_modes = ["verilog_memory"]
            memory_flop_limits = [None, 128]
            memory_max_widths = [None, 4, 7]
            memory_max_depths = [None, 64, 256]
            dmult = 50
        elif mode == "vm_short":
            if is_async:
                memory_ports = [2]
            else:
                memory_ports = [1, 2]
            technologies = ['asic', 'fpga']
            memory_modes = ["verilog_memory"]
            memory_flop_limits = [None]
            memory_max_widths = [None]
            memory_max_depths = [None]
            dmult = 50
        elif mode == "tsmc":
            memory_modes = ["tsmc_cln40g", "tsmc_cln16fpll"]
            memory_flop_limits = [128]
            memory_max_widths = [None]
            memory_max_depths = [None]
        elif mode == "custom":
            if is_async:
                memory_ports = [2]
            else:
                memory_ports = [1, 2]
            technologies = ['asic']
            memory_modes = ["verilog_memory"]
            memory_flop_limits = [10000]
            memory_max_widths = [8]
            memory_max_depths = [8]
            dmult = 5
        else:
            assert False

        if init and not wide and not merge and not mport:
            print("init True")
            modName = "modules.common.memory"
            blockName = "memory_init"
        elif is_async:
            print("init False")
            memory_wt = [0]
            modName = "modules.common.memory"
            blockName = "memory"
        elif wide:
            print("Overclock Wide mode")
            # write_through = [0 for _ in range(len(depths))]
            modName = "modules.common.memory_overclock_wide"
            blockName = "memory_overclock_wide"
            min_signal_width = 8
            max_signal_width = 256
            min_depth = 2
            max_depth = 128
            dmult = 50
            force_latencies = [None, 1, 2, 3]
        elif merge:
            print("Overclock Merge mode")
            memory_iflops = [0, 1]
            memory_oflops = [0, 1]
            modName = "modules.common.memory_overclock_merge"
            blockName = "memory_overclock_merge"
            memory_insts = range(2, 10)
            force_latencies = [None, 1, 2, 3]
            dmult = 100
            if duration != "short":
                max_depth = 128
            else:
                force_latencies = [3]
                memory_insts = [2]
        elif mport:
            print("Overclock Multi-port mode")
            memory_wt = [0]
            memory_iflops = [0, 1]
            memory_oflops = [0, 1]
            modName = "modules.common.memory_overclock_ports"
            blockName = "memory_overclock_ports"
            memory_ports = range(2, 9)
            force_latencies = [None, 1, 2, 3]
            dmult = 512
            if duration == "short":
                memory_iflops = [0]
                memory_oflops = [0]
                memory_ports = [2]
                force_latencies = [2]
        elif multi:
            print("Multi-access mode")
            memory_wt = [0, 1]
            memory_iflops = [0, 1]
            memory_oflops = [0, 1]
            modName = "modules.common.memory_multi_access"
            blockName = "memory_multi_access"
            memory_ports = range(2, 9)
            if duration == "short":
                memory_wt = [1]
                memory_iflops = [1]
                memory_oflops = [1]
                memory_ports = [8]
        else:
            print("init False")
            modName = "modules.common.memory"
            blockName = "memory"
            wmask = [True, None]
            
        if mode == "custom":
            wmask = [True]

        pre_load = 0
        conf_load = {}
        # Test signalmode

        widths = random.sample(
            range(min_signal_width, max_signal_width), number_of_configurations
        )
        depths = random.sample(range(min_depth, max_depth), len(widths))

        pre_load = [randrange(1 + init) for _ in range(len(depths))]
        lat = [random.choice(force_latencies) for _ in range(len(depths))]
        ifl = [random.choice(memory_iflops) for _ in range(len(depths))]
        ofl = [random.choice(memory_oflops) for _ in range(len(depths))]
        ths = [random.choice(technologies) for _ in range(len(depths))]
        mos = [random.choice(memory_modes) for _ in range(len(depths))]
        fls = [random.choice(memory_flop_limits) for _ in range(len(depths))]
        mws = [random.choice(memory_max_widths) for _ in range(len(depths))]
        mds = [random.choice(memory_max_depths) for _ in range(len(depths))]
        prt = [random.choice(memory_ports) for _ in range(len(depths))]
        ins = [random.choice(memory_insts) for _ in range(len(depths))]
        div = [0 for _ in range(len(depths))]
        wms = [random.choice(wmask) for _ in depths]
        write_through = [random.choice(memory_wt) for _ in range(len(depths))]

        if wide:
            div = [2]
            for i in range(len(widths) - 1):
                div.append(randrange(widths[i] - 1) + 2)
            print("Divisors: ", div)

        if merge == True:
            div = [randrange(2, i + 3) for i in ins]  # [ i+1 for i in ins ] #
            # When there is no overclocking the force latency is not valid
            for i in range(len(widths)):
                if prt[i] == 1:
                    lat[i] == None
                widths[i] = [widths[i] for _ in range(ins[i])]
        if mport == True:
            div = [i for i in prt]
            for i in range(len(widths)):
                widths[i] = [widths[i] for _ in range(prt[i])]
        if multi == True:
            for i in range(len(widths)):
                widths[i] = [widths[i] for _ in range(prt[i])]

        if merge == True or mport == True or wide == True:

            # Force latency cannot be lower than the native latency
            for i in range(len(widths)):
                clat = memory_latency(ifl[i], ofl[i], div[i], wide, mport, merge)
                if lat[i] != None:
                    if clat > lat[i]:
                        lat[i] = clat

        for i in range(len(prt)):
            if prt[i] == 1:
                write_through[i] = 0
        print("widths", widths, flush=1)
        for w, d, wt, pl, th, mo, fl, mw, md, p, i, dv, mif, mof, lt, wm in zip(
            widths,
            depths,
            write_through,
            pre_load,
            ths,
            mos,
            fls,
            mws,
            mds,
            prt,
            ins,
            div,
            ifl,
            ofl,
            lat,
            wms,
        ):
            if wide or (
                merge and i % dv == 1
            ):  # The wide mems have limited reset value support (and single instances in merge use wide)
                print(
                    f"Resticting the reset value to 0 or -1 due to wide {wide}, "
                    f"merge {merge}, ports {i}, div {dv}, ports mod div {i % dv}. "
                    f"Width {w}"
                )
                if merge:
                    wtemp = w[0]
                else:
                    wtemp = w
                if randrange(2):
                    reset_value = 0
                else:
                    reset_value = (1 << wtemp) - 1
            elif merge or mport or multi:
                reset_value = randrange(2 ** w[0] - 1)
            else:
                reset_value = randrange(2**w - 1)
            if mw and w > mw:
                # No write mask when slicing into columns
                wm = None
            if p == 1:
                # No write mask support for single ported memory yet
                wm = None
            if wm and w > 1:
                wt = 0
                for x in range(8, 0, -1):
                    if w % x == 0 and w != x:
                        wm_w = w // x
                        break
                wmask = wm_w
            else:
                wmask = None
            hwc = Hwc(
                memory_flop_limit=fl,
                technology=th,
                memory_mode=mo,
                memory_max_width=mw,
                memory_max_depth=md,
                memory_force_input_flop=0,
                memory_force_output_flop=0,
                memory_force_in_or_out_flop=0,
            )
            wstr = (
                str(w)
                .replace(" ", "")
                .replace(",", "_")
                .replace("[", "")
                .replace("]", "")
            )
            self.runSimulation(
                testbench,
                modName,
                blockName,
                f"_w{wstr}_d{d}_wt{wt}_pl{pl}_th{th}_p{p}_i{i}_dv{dv}_if{mif}_of{mof}"
                f"_lt{lt}_wm{wmask}",
                w,
                d,
                reset_value,
                wt,
                pl,
                is_async,
                dv,
                i,
                hwc,
                p,
                multi,
                mif,
                mof,
                lt,
                int(d * dmult),
                wmask,
            )
        # Test listmode
        if lmode:
            hwc = Hwc()
            widths = [
                random.sample(
                    range(1, max_signal_width_in_list),
                    random.randint(2, max_list_width),
                )
                for x in range(number_of_configurations)
            ]
            depths = random.sample(range(2, max_depth), len(widths))
            if init == False:
                for w, d, wt, mif, mof in zip(widths, depths, write_through, ifl, ofl):
                    wstr = (
                        str(w)
                        .replace(" ", "")
                        .replace(",", "_")
                        .replace("[", "")
                        .replace("]", "")
                    )
                    self.runSimulation(
                        testbench,
                        modName,
                        blockName,
                        f"_w{wstr}_d{d}_wt{wt}_if{mif}_of{mof}_lt{lt}",
                        w,
                        d,
                        0,
                        wt,
                        0,
                        is_async,
                        0,
                        1,
                        hwc,
                        2,
                        multi,
                        mif,
                        mof,
                        lt,
                        int(d * dmult),
                        None,
                    )


if __name__ == "__main__":
    unittest.main()
