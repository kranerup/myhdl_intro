from . import fake_hwconf  # noqa: F401
from modules.common.tcam.tcam import tcam_bus
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from tb.coco.setup import cocotb_setup, myhdl_verilog, dbgprint
from modules.conf.confif import ConfIf
from tb.coco.bfm.conf_bfm import ConfMaster, ACCUMULATOR, DEFAULT
from modules.common.signal import signal
from modules.common.hwconf import get_hwconf
from random import randrange, sample, choice
from pytest import mark
from os.path import dirname, abspath, exists
from os import mkdir
from glob import glob
from time import sleep


hwconf = get_hwconf()
this = dirname(abspath(__file__))


CDSIZE = hwconf.conf_data_width
CDMASK = (1 << CDSIZE) - 1
IDBITS = max((hwconf.nr_of_id - 1).bit_length(), 1)
START_ADDR = 64


def mk_config(
    key_bits,
    depth,
    cam_model,
    latency,
    cam_mask=True,
    key_mask=True,
    miss_max=False,
    nr_id=None,
):
    _depth = depth
    entry_bits = key_bits + 1 + (key_bits if cam_mask else 0)
    entry_words = (entry_bits + CDSIZE - 1) // CDSIZE
    idxbits = (depth - 1).bit_length()
    kmask = (1 << key_bits) - 1

    input_flops = int(latency > 1)
    output_flops = int(latency == 3)

    if not nr_id:
        nr_id = 32

    class settings:
        start_address = START_ADDR
        end_address = START_ADDR + _depth * entry_words

        def depth():
            return depth

    copy_files = []
    if cam_model == "cavium":
        copy_files = ["cam_ternary.sv"]
    elif cam_model == "es":
        copy_files = ["TCAM*.v"]

    tname = (
        f"{cam_model}_k{key_bits}_d{depth}_l{latency}"
        f"_cm{int(cam_mask)}_km{int(key_mask)}"
    )

    key_input_bits = key_bits * (2 if key_mask else 1)

    def create_dut():
        clk = signal()
        rstn = signal()
        confbus = ConfIf(CDSIZE, 32, IDBITS)

        cam_search = signal()
        cam_key = signal(key_input_bits)
        cam_answer = signal(idxbits + 1)
        _cam_mask = cam_mask
        _key_mask = key_mask

        hdldir = "../../hdl"

        if not exists(hdldir):
            try:
                mkdir(hdldir)
            except FileExistsError:
                pass

        hwconf._hwconf.cam_model = cam_model
        hwconf._hwconf.nr_of_id = nr_id

        myhdl_verilog(
            tcam_bus,
            clk=clk,
            rstn=rstn,
            confbus=confbus,
            settings=settings,
            cam_search=cam_search,
            cam_key=cam_key,
            cam_answer=cam_answer,
            cam_mask=_cam_mask,
            key_mask=_key_mask,
            input_flops=input_flops,
            output_flops=output_flops,
            name="dut",
        )

        copied_files = []
        for p in copy_files:
            for g in glob(f"{hdldir}/{p}"):
                d = g.replace(f"{hdldir}/", "", 1)
                with open(g) as src, open(d, "w") as dst:
                    dst.write(src.read())
                copied_files.append(d)

        return ["tcam_bus.v", *copied_files]

    _build, _run_test = cocotb_setup(
        "tcam_bus",
        "modules.common.tcam.tests.test_tcam",
        create_dut,
        wdname=f"tcam_bus_{tname}",
        scope=None,
    )

    class Test:
        build = staticmethod(_build)
        run_test = staticmethod(_run_test)

        @mark.parametrize("testcase", [f"smoke_{tname}", f"pattern_{tname}"])
        def test_dut(self, testcase, build):
            self.run_test(testcase, build)
            sleep(5)

    globals()[f"Test_{tname}"] = Test

    class TB:
        def __init__(self, dut, name, clock_period_ns=10):
            self.dut = dut
            self.name = name
            dut.rstn.setimmediatevalue(1)
            self.clock_period_ns = clock_period_ns
            clock = Clock(dut.clk, clock_period_ns, "ns")
            cocotb.start_soon(clock.start())
            cocotb.start_soon(self._search_answer())
            self.conf = ConfMaster(
                dut,
                "confbus_request",
                "confbus_reply",
                dut.clk,
                dut.rstn,
                nr_id,
            )
            self.searches = []
            self.chk_cnt = 0
            self.clock = RisingEdge(dut.clk)

        async def reset(self):
            dut = self.dut
            dut.rstn.value = 0
            dut.cam_search.value = 0
            dut.cam_key.value = 0
            for _ in range(5):
                await self.clock
            self.dut.rstn.value = 1
            await self.clock

        async def write(self, idx, key, mask=0, en=1):
            key &= kmask
            mask &= kmask
            dbgprint(f"write {idx:#x} key={key:#x} mask={mask:#x} en={en}")
            if cam_mask:
                data = key | (mask << key_bits) | (en << (2 * key_bits))
            else:
                data = key | (en << key_bits)
            resp = []
            for i in range(entry_words):
                type = ACCUMULATOR if i != (entry_words - 1) else DEFAULT
                dword = (data >> (i * CDSIZE)) & CDMASK
                resp.append(
                    await self.conf.write_rq(
                        START_ADDR + idx * entry_words + i, dword, type=type
                    )
                )
                while randrange(0, 100) < 5:
                    await self.clock
            for r in resp:
                await r.wait()

        async def read(self, idx):
            data = 0
            resp = []
            for i in range(entry_words):
                type = ACCUMULATOR if i != 0 else DEFAULT
                resp.append(
                    await self.conf.read_rq(
                        START_ADDR + idx * entry_words + i, type=type
                    )
                )
                while randrange(0, 100) < 5:
                    await self.clock
            for i, r in enumerate(resp):
                _, dword = await r.wait()
                data |= dword << (i * CDSIZE)
            if cam_mask:
                rv = (
                    data & kmask,
                    (data >> key_bits) & kmask,
                    (data >> (2 * key_bits)) & 1,
                )
            else:
                rv = (data & kmask), 0, ((data >> key_bits) & 1)
            dbgprint(f"read {idx:#x} key={rv[0]:#x} mask={rv[1]:#x} en={rv[2]}")
            return rv

        async def search(self, key, mask=0, exp=None):
            key &= kmask
            mask &= kmask
            dut = self.dut
            dut.cam_search.value = 1
            self.searches.append((exp, key, mask))
            if not key_mask:
                mask = 0
            dut.cam_key.value = key | (mask << key_bits)
            dbgprint(f"search key={key:#x} mask={mask:#x}")
            await self.clock
            dut.cam_search.value = 0
            dut.cam_key.value = 0

        async def _search_answer(self):
            fifo = 0
            fifo_mask = (1 << (latency + 1)) - 1
            dut = self.dut
            while True:
                await self.clock
                fifo = ((fifo << 1) | int(dut.cam_search.value)) & fifo_mask
                if (fifo >> latency) & 1:
                    v = int(dut.cam_answer.value)
                    (ehit, eidx), k, m = self.searches.pop(0)
                    hit = bool(v & 1)
                    idx = v >> 1
                    dbgprint(
                        f"answer k={k:#x} km={m:#x} ans={v:#x} "
                        f"hit={hit}/{ehit} idx={idx}/{eidx}"
                    )
                    assert hit == ehit
                    if hit:
                        assert idx == eidx
                    self.chk_cnt += 1

        async def end(self, chk_cnt=None):
            for _ in range(latency + 4):
                await self.clock
            if chk_cnt is not None:
                assert self.chk_cnt == chk_cnt

    @cocotb.test()
    async def smoke(dut):
        tb = TB(dut, "smoke")
        await tb.reset()
        entries = [0, *sample(range(1, depth - 1), 10), depth - 1]
        for i, e in enumerate(entries):
            await tb.write(e, i + 10)
        for i, e in enumerate(entries):
            assert (await tb.read(e)) == (i + 10, 0, 1)
        for i, e in enumerate(entries):
            await tb.search(i + 10, exp=(True, e))
            await tb.search(i + 100, exp=(False, 0))
        await tb.write(0, 42)
        await tb.write(depth - 1, 42)
        await tb.search(42, exp=(True, 0))
        await tb.end(25)

    globals()[f"smoke_{tname}"] = smoke

    def rotl(x, bits, amount=1):
        """rotate left"""
        mask = (1 << bits) - 1
        if amount > 0:
            return (x << amount) & mask | (x >> (bits - amount))
        else:
            return (x >> -amount) | (x << (bits + amount)) & mask

    def rnd_mask(not_bit, cnt=4):
        bits = [not_bit]
        while not_bit in bits:
            bits = sample(range(key_bits), cnt)
        return sum(1 << i for i in bits)

    @cocotb.test()
    async def pattern(dut):
        tb = TB(dut, "pattern")
        miss = False, (depth - 1 if miss_max else 0)
        await tb.reset()
        # Write all entries, and read back a few
        for i in range(depth):
            await tb.write(i, i + 10)
        for i in [0, *sample(range(1, depth-1), 10), depth-1]:
            assert (await tb.read(i)) == (i + 10, 0, 1)

        # Hit and miss each entry
        for i in range(depth):
            await tb.search(i + 10, exp=(True, i))
            await tb.search(~(i + 10), exp=(False, 0))

        # Disable all entries, and then make sure they do not hit
        for i in range(depth):
            await tb.write(i, 10, en=0)
        await tb.search(10, exp=(False, 0))

        chk_cnt = 2 * depth + 1

        # Test all key and mask bits, using random entry
        e = choice(range(depth))
        hit = (True, e)
        miss = (False, 0)
        for i in range(key_bits):
            await tb.write(e, 1 << i)
            await tb.search(1 << i, exp=hit)
            await tb.search(rotl(1 << i, key_bits, 1), exp=miss)
            await tb.search(rotl(1 << i, key_bits, -1), exp=miss)
            chk_cnt += 3
            if cam_mask:
                await tb.write(e, 1 << i, ~(1 << i))
                await tb.search(1 << i, exp=hit)
                await tb.search(rotl(1 << i, key_bits, 1), exp=miss)
                await tb.search(rotl(1 << i, key_bits, -1), exp=miss)
                await tb.search(rotl(1 << i, key_bits, 1) | 1 << i, exp=hit)
                await tb.search(rotl(1 << i, key_bits, -1) | 1 << i, exp=hit)
                await tb.search(kmask, exp=hit)
                await tb.write(e, 1 << i, kmask)
                await tb.search(0, exp=hit)
                await tb.search(kmask, exp=hit)
                m = rnd_mask(i)
                await tb.write(e, 1 << i, m)
                await tb.search(1 << i, exp=hit)
                await tb.search(1 << i | m, exp=hit)
                await tb.search(1 << i | (kmask ^ m), exp=miss)
                for j in range(key_bits):
                    v = 1 << j | 1 << i
                    if ((1 << j) & m) or i == j:
                        await tb.search(v, exp=hit)
                    else:
                        await tb.search(v, exp=miss)

                chk_cnt += 11 + key_bits
            if key_mask:
                await tb.write(e, 1 << i)
                m = ~(1 << i)
                await tb.search(1 << i, m, exp=hit)
                await tb.search(rotl(1 << i, key_bits, 1), m, exp=miss)
                await tb.search(rotl(1 << i, key_bits, -1), m, exp=miss)
                await tb.search(rotl(1 << i, key_bits, 1) | 1 << i, m, exp=hit)
                await tb.search(rotl(1 << i, key_bits, -1) | 1 << i, m, exp=hit)
                await tb.search(kmask, m, exp=hit)
                await tb.search(0, kmask, exp=hit)
                await tb.search(kmask, kmask, exp=hit)
                chk_cnt += 8

        tb.write(e, 0, en=0)
        # Test priority
        entries = sorted(sample(range(0, depth), 4))
        for e in entries:
            await tb.write(e, 42)
        for e in entries:
            await tb.search(42, exp=(True, e))
            await tb.write(e, 42, en=0)
        chk_cnt += 4

        await tb.end(chk_cnt)

    globals()[f"pattern_{tname}"] = pattern


# Put long tests first to improve runtime when running in parallel
mk_config(160, 1024, "es", 3)
mk_config(160, 3601, "es", 3)  # depth stacking
mk_config(163, 1028, "es", 2)  # depth and width stacking
mk_config(80, 512, "es", 3)
mk_config(170, 256, "es", 2)

mk_config(160, 64, "default", 1)
mk_config(160, 64, "default", 1, cam_mask=False, nr_id=1)
mk_config(160, 64, "default", 1, key_mask=False)
mk_config(160, 64, "default", 1, cam_mask=False, key_mask=False)
mk_config(160, 64, "default", 2)
mk_config(160, 64, "default", 3)
mk_config(160, 64, "cavium", 3, miss_max=True)
mk_config(160, 64, "es", 3)
mk_config(160, 64, "es", 2)
mk_config(160, 64, "es", 3, cam_mask=False)
mk_config(160, 64, "es", 3, key_mask=False)
mk_config(160, 64, "es", 3, cam_mask=False, key_mask=False)
mk_config(161, 64, "es", 3)
mk_config(66, 64, "es", 3, key_mask=False)
mk_config(66, 64, "es", 3)
mk_config(320, 64, "es", 3)
mk_config(321, 64, "es", 3)
mk_config(50, 65, "es", 3)
mk_config(80, 65, "es", 3)
mk_config(81, 65, "es", 3)
