from myhdl import always, always_comb, instances, connect
from .Common import signalType, listType
from .Common import compoundWidth
from .memory import memory
from .fifo_memlat import fifo_signal_memlat
from .signal import signal, sigarray


"""
The fifo only supports keeping the valid data on the
outputs until pop. This is very nice for design, but the timing is
worse than for a fifo that reads the memory at pop.

Anyway, none of these methods infer a hardware FIFO in Altera or
Xilinx (as far as I'm aware), and at least for Xilinx all block ram
has hardware support for working as a FIFO. Inferring this would
certainly be best both resource wize and timing wize, but I have not
investigated how to accomplish that. Most probably we need to use
vendor specific instantiation templates.

The FIFO also only supports same width in and out, and only a single
clock.

"""


# fifo_imp is a wrapper containing the consistency check, and the
# selecting between the different fifo implementations.
def fifo_imp(
    idata,
    odata,
    push,
    pop,
    full,
    empty,
    level,
    clk,
    rstn,
    clear=0,
    depth=4,
    consistency_check=None,
    memoryMode="mem",
    memory_input_flops="default",
    memory_output_flops="default",
    name="",
):
    # clear is used as an optional signal to reset/restart the fifo

    print(
        f"Instanciated fifo_imp {name} with depth {depth}, "
        f"memory_input_flops {memory_input_flops}, "
        f"memory_output_flops {memory_output_flops}, memoryMode {memoryMode}"
    )

    # future check if level is a modbv
    if False and ("modbv" not in str(getattr(level, "_handleBounds"))):
        print("ERROR, the fifo signal 'level' need to be a modbv")
        assert False

    # optional check mechanism to investigate if fifo is empty
    if signalType(consistency_check):
        print(name, "is using consistency_check")
        assert_ccheck = signal()

        @always(clk.posedge, rstn.negedge)
        def ccheck():
            if rstn == 0:
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
                        assert False, ("%s Consistency check FAILED! level %s" % (name, level))
                        "synthesis translate_on"

    iflat = idata
    if listType(idata):
        iflat = signal(compoundWidth(idata))
        iflat_conv = connect(iflat, idata)  # noqa: F841
    oflat = odata
    if listType(odata):
        oflat = signal(compoundWidth(odata))
        oflat_conv = connect(odata, oflat)  # noqa: F841

    if memory_input_flops + memory_output_flops > 0 and memoryMode == "mem":
        iFifoml = fifo_signal_memlat(  # noqa: F841
            iflat,
            oflat,
            push,
            pop,
            full,
            empty,
            level,
            clk,
            rstn,
            memory_input_flops,
            memory_output_flops,
            0,
            depth,
            consistency_check,
            name=name + ".iFifoml",
        )
    elif memory_input_flops + memory_output_flops == 0 or memoryMode == "ff":
        iFifos = fifo_signal(  # noqa: F841
            iflat,
            oflat,
            push,
            pop,
            full,
            empty,
            level,
            clk,
            rstn,
            clear,
            depth,
            memoryMode,
            name=name + ".iFifos",
        )
    else:
        print(
            f"ERROR! {name} unsupported combination flops "
            f"{memory_input_flops}+{memory_output_flops} and mode {memoryMode}"
        )
        assert False
    return instances()


# fifo_counters creates the level, full and empty signals, and is
# reused in several fifo implementations
def fifo_counters(
    push, pop, dirty_level, dirty_empty, full, clear, clk, rstn, depth, name=""
):
    push_full = signal(debug_level=1)
    pop_empty = signal(debug_level=1)

    @always(clk.posedge, rstn.negedge)
    def count():
        if rstn == 0:
            dirty_level.next = 0
            full.next = 0
            dirty_empty.next = 1
            push_full.next = 0
            pop_empty.next = 0
        else:
            if clear:
                full.next = 0
                dirty_level.next = 0
                dirty_empty.next = 1
            else:
                if push == 1 and pop == 0:
                    if full == 1:
                        push_full.next = 1
                        assert False, "ERROR pushing to full FIFO %s" % name
                    else:
                        dirty_level.next = dirty_level + 1
                    if dirty_level == depth - 1:
                        full.next = 1
                    dirty_empty.next = 0
                if push == 0 and pop == 1:
                    if dirty_empty == 1:
                        pop_empty.next = 1
                        assert False, "ERROR popping empty FIFO %s" % name
                    else:
                        dirty_level.next = dirty_level - 1
                    full.next = 0
                    if dirty_level == 1:
                        dirty_empty.next = 1

    return instances()


# Fifo signal is the basic fifo implementation. It supports both
# memory and FF modes, but not memory latency above 1
def fifo_signal(
    idata,
    odata,
    push,
    pop,
    full,
    empty,
    level,
    clk,
    rstn,
    clear=0,
    depth=4,
    memoryMode="mem",
    name="",
):
    print(
        f"Instanciated fifo_signal {name} with depth {depth} and "
        f"memoryMode {memoryMode}"
    )
    w = len(idata)

    ptr_w = (depth - 1).bit_length()
    print(f"fifo_imp: {name} depth {depth}, ptr_w {ptr_w}")
    head = signal(ptr_w)
    tail = signal(ptr_w)

    if memoryMode == "ff":
        data = sigarray(w, depth)

        @always_comb
        def driveOut():
            odata.next = data[head]

        @always(clk.posedge, rstn.negedge)
        def fill():
            if rstn == 0:
                for i in range(len(data)):
                    data[i].next = 0
                head.next = depth - 1
                tail.next = 0
            else:
                if push:
                    data[tail].next = idata
                    tail.next = (tail + 1) % depth
                    if empty:
                        head.next = (head + 1) % depth
                if pop:
                    if level > 1 or push == 1:
                        # Reduce output toggle by not moving tail when going empty
                        head.next = (head + 1) % depth
                if clear:
                    head.next = depth - 1
                    tail.next = 0

    elif memoryMode == "mem":
        odata_reg = signal(w)
        odata_mem = signal(w)
        odata_sel = signal()
        mem_re = signal()
        mem_we = signal()

        @always_comb
        def fifo_output_select():
            if odata_sel:
                odata.next = odata_mem
            else:
                odata.next = odata_reg

        @always_comb
        def mem_read():
            mem_re.next = 0
            if pop == 1 and level > 1:
                mem_re.next = 1

        @always_comb
        def mem_write():
            mem_we.next = int(push == 1 and not (empty == 1 or level == 1 and pop == 1))

        @always(clk.posedge, rstn.negedge)
        def fifo_output():
            if rstn == 0:
                odata_sel.next = 0
                odata_reg.next = 0
                head.next = 0
                tail.next = 0
            else:
                odata_sel.next = mem_re
                if mem_re:
                    head.next = (head + 1) % depth
                if odata_sel:
                    odata_reg.next = odata_mem
                if push:
                    if empty == 1 or level == 1 and pop == 1:
                        odata_reg.next = idata
                    else:
                        tail.next = (tail + 1) % depth
                if clear:
                    odata_sel.next = 0
                    head.next = 0
                    tail.next = 0
                assert tail == head or empty == 0, "ERROR %s %s %s" % (
                    tail,
                    head,
                    empty,
                )
                assert (head + level) % depth == (
                    tail + 1
                ) % depth or empty == 1, "ERROR t=%s h=%s l=%s e=%s" % (
                    tail,
                    head,
                    level,
                    empty,
                )

        mem = memory(  # noqa: F841
            idata,
            odata_mem,
            head,
            tail,
            mem_re,
            mem_we,
            clk,
            rstn,
            depth=depth,
            write_through=1,
            name=name + ".mem",
        )
    else:
        assert False, f"ERROR! Unsupported memoryMode {memoryMode} for fifo {name}"

    zFcnt = fifo_counters(  # noqa: F841
        push, pop, level, empty, full, clear, clk, rstn, depth, name=f"{name}.zFcnt"
    )

    return instances()
