from myhdl import (
    Simulation,
    traceSignals,
    toVerilog,
    always_comb,
    instance,
    delay,
    instances
)
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator

def test_bench():

    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    cgen = clock_reset_generator( clk, sync_rstn )

    # instead of the handcrafted flipflop we now use a flop from the common library
    dut = sflop( i=next_state, o=state, clk_en=None, clk=clk, sync_rstn=sync_rstn )

    @instance
    def stimuli():
        next_state.next = 0
        yield clk.negedge

        for i in range(4):
            next_state.next = i
            print("next_state:%d" %(next_state))
            yield clk.negedge
            print("state:%d" %(state))

    return instances()

traceSignals.filename = 'trace'
wave_tb = traceSignals( test_bench ) 
sim = Simulation(wave_tb)
sim.run(100)


clk        = signal()
sync_rstn  = signal()
state      = signal(2)
next_state = signal(2)

toVerilog.standard = 'systemverilog'
itop = toVerilog( sflop, next_state, state, None, clk, sync_rstn )

