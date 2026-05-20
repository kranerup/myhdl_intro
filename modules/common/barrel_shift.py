from myhdl import *
from .Common import pass_through, sliceSignal, signalType, listType, copySignal, mux2, flop, compoundWidth, pipeline
from math import ceil
import sys

"""
File status: The barrel shifter needs to be updated to support a
halt-bit in order not to flood the blocks it is feeding when the
pipeline depth is deep.
"""

# A barrel shifter of configurable pipeline depth

def shift_pipe(data_in, data_out, shift, id_in, id_out,clk, rstn, 
               step        = 8,
               pre_flops   = 1,
               latency     = 1,
               mux_depth = 1,
               mux_width   = 4,
               direction   = 'up',
               max_shift   = 1,
               name        = '' ):

    print("Instanciated shift_pipe %s with direction %s, step %d, latency %d, mux_depth %d, mux_width %d and max_shift %d" %( name, direction, step, latency, mux_depth, mux_width, max_shift))
    sys.stdout.flush()

    din = Signal(intbv(0)[compoundWidth(data_in):0])
    zpassin = pass_through(data_in, din, name=name+".din")

    dout = Signal(intbv(0)[compoundWidth(data_out):0])
    zpassout = pass_through(dout, data_out, name=name+".dout")

    assert mux_width & (mux_width-1) == 0, "ERROR %s. mux_width needs to be power of 2. mux_width = %d" %( name, mux_width )

    cnt = 1
    mux_stages = 0
    while(cnt<=max_shift):
        cnt    *= mux_width
        mux_stages += 1
    
    pipe_latency = mux_stages // mux_depth
    mux_width_w = (mux_width-1).bit_length()
    mux_mask = (1<<mux_width_w) - 1
    pipe_latency += pre_flops
    print("shift_pipe %s, pipe_latency %d, latency %d, mux_stages %d" % (name, pipe_latency, latency, mux_stages))

    assert pipe_latency <= latency

    inst = shift_up
    if direction=='down':
        inst      = shift_down

    shiftwire = []
    idwire = []
    wire = []
    zshift      = []
    zpass       = []
    zflop       = []

    shiftwire.append(copySignal(shift))
    zpass.append(pass_through(shift, shiftwire[0], name=name+".pass_sh"))
    for l in range(pipe_latency+pre_flops):
        shiftwire.append(copySignal(shift))
        zflop.append(flop(shiftwire[l], shiftwire[l+1], clk, rstn, name=name+".shflop%d"%l))
        
    shift_vector = [Signal(intbv(0, min=0, max=mux_width)) for _ in range(mux_stages)]
    @always_comb
    def shve():
        mcnt = 0
        for f in range(pipe_latency+1):
            for m in range(mux_depth):
                if mcnt < mux_stages:
                    shift_vector[mcnt].next = (shiftwire[f+pre_flops] >> (mcnt*mux_width_w)) & mux_mask
                    mcnt += 1

    inw  = len(data_in)
    ww   = inw
    outw = len(data_out)
    wire.append(Signal(intbv(0)[ww:0]))
    idwire.append(copySignal(id_in))
    zpass.append(pass_through(din, wire[0], allow_mismatch=1, name=name+".pass_in"))
    zpass.append(pass_through(id_in, idwire[0], name=name+".pass_id"))
    wire_cnt = 0
    flop_cnt = 0
    step_value = step 
    step_cnt = 0
    for l in range(latency):
        if l >= pre_flops:
            for d in range(mux_depth):
                if step_cnt<mux_stages:
                    ww += step_value<<len(shift_vector[step_cnt])
                    if ww > outw:
                        ww = outw
                    wire.append(Signal(intbv(0)[ww:0]))
                    print(name, "shift mux", flop_cnt, "step", step_cnt, "val", step_value, "wire", wire_cnt)
                    zshift.append(inst(
                        data_in  = wire[wire_cnt],
                        data_out = wire[wire_cnt+1],
                        shift    = shift_vector[step_cnt],
                        step     = step_value,
                        name     = name+".shift"+str(step_cnt)
                        ))
                    wire_cnt += 1
                    step_cnt += 1
                    step_value = step_value << mux_width_w
                else:
                    break
        print(name, "flop flop", flop_cnt, "step", step_cnt, "val", step_value, "wire", wire_cnt)
        wire.append(Signal(intbv(0)[ww:0]))
        idwire.append(copySignal(id_in))
        zflop.append(flop(idwire[flop_cnt], idwire[flop_cnt+1], clk, rstn, name=name+".idflop%d"%l))
        zflop.append(flop(wire[wire_cnt], wire[wire_cnt+1], clk, rstn, name=name+".flop%d"%l))
        wire_cnt += 1
        flop_cnt += 1
    zpass.append(pass_through(wire[wire_cnt], dout, allow_mismatch=1, name=name+".pass_out"))
    zpass.append(pass_through(idwire[flop_cnt], id_out, name=name+".pass_id"))

    return instances()

def shift_up(data_in, data_out, shift, step=8, name=''):
    wo = compoundWidth(data_out)
    @always_comb
    def upshiftproc():
        mask = intbv(-1)[wo:]
        data_out.next = (data_in << (shift*step)) & mask
    return instances()

def shift_down(data_in, data_out, shift, step=8, name=''):
    wo = compoundWidth(data_out)
    @always_comb
    def dnshiftproc():
        mask = intbv(-1)[wo:]
        data_out.next = data_in >> (shift*step) & mask
    return instances()
