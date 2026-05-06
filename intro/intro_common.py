from myhdl import (
    instance,
    delay,
    instances
)
def clock_reset_generator(clk, sync_rstn, period=20):

    high_time = int(period/2)
    low_time = period - high_time

    @instance
    def clk_logic():
        while True:
            yield delay(low_time)
            clk.next = 1
            yield delay(high_time)
            clk.next = 0

    @instance
    def reset():
        sync_rstn.next = 0
        yield clk.negedge
        sync_rstn.next = 1

    return instances()

