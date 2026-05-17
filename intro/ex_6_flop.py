from myhdl import *
from modules.common.signal import signal
from modules.common.Common import sflop
from intro_common import clock_reset_generator

def test_bench():

    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    cgen = clock_reset_generator( clk, sync_rstn )

    # Instead of the handcrafted flipflop from previous examples 
    # we will now use a flipflop from the common library.
    # We're now also connecting sync_rstn which is a reset signal
    # that should reset the design to it's initial state when it is
    # set to 0. This is a synchronous reset signal.
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

if __name__ == "__main__":
    # Simulate the design.
    traceSignals.filename = 'trace'
    wave_tb = traceSignals( test_bench ) 
    sim = Simulation(wave_tb)
    sim.run(100)

    # Generate the Verilog.
    clk        = signal()
    sync_rstn  = signal()
    state      = signal(2)
    next_state = signal(2)

    toVerilog.standard = 'systemverilog'
    itop = toVerilog( sflop, next_state, state, None, clk, sync_rstn )

    # Look at the Verilog file sflop.v. In the always_ff block the
    # 'o' signal is set to 0 when sync_rstn is 0. This can also
    # be seen in the sflop definition in Common.py.
