from myhdl import *
import random 
import unittest
from unittesting.ClockedTestCase import *
from .Common import value, pipeline, copySignal
from .free import free
import sys

class UnitTest(unittest.TestCase, ClockedTestCase):
    def setUp(self):
        super(UnitTest, self).setUpSeed()

    def test_free(self):
        mod_name = 'modules.common.free'
        block_name = 'free'
        module = free
        self.run_test_free(mod_name, block_name, module)
        
    def run_test_free(self, mod_name, block_name, module):
        # The testbench needs to have the parameters cosim and synt,
        # and they have to be set as false by default

        # It needs to be named testbench
        def testbench(mod_name, block_name, postfix,
                      depth=5, fm_width=16, mode='default', nr=5,
                      cosim=False, synt=False):

            # automatic terminator
            # will end simulations where exit criteria is not triggered
            # sim_time.max decides the time for automatic termination
            # 2**25 appear to provide enough cycles for test to finish
            terminator = Signal(intbv(0)[1:0])
            phase_log = Signal(intbv(0)[1:0])
            full_log = Signal(intbv(0)[1:0])
            full_hyst_log = Signal(intbv(0)[1:0])
            empty_log = Signal(intbv(0)[1:0])
            empty_hyst_log = Signal(intbv(0)[1:0])
            pp_log = Signal(intbv(0)[1:0])
            prob_log = Signal(intbv(0)[1:0])
            sim_time = Signal(intbv(0, max=2**25)) 

            clk   = Signal(intbv(0)[1:0]) 
            rstn  = Signal(intbv(0)[1:0]) 

            time_step = 10
            
            # Generate clock and reset
            @instance
            def rstn_gen():
                terminator.next = 1 # terminator on/off
                sim_time.next = 0
                rstn.next = 0
                yield delay(103)
                rstn.next = 1

            @always(delay(time_step))
            def clk_gen():
                if terminator==1:
                    sim_time.next = sim_time + 1
                clk.next = not clk

            @always_comb
            def log_log():
                # logging on/off
                phase_log.next = 0 & terminator
                full_log.next = 0 & terminator
                full_hyst_log.next = 0 & terminator
                empty_log.next = 0 & terminator
                empty_hyst_log.next = 0 & terminator
                pp_log.next = 0 & terminator
                prob_log.next = 0 & terminator

            # Declare the rest of the signals
            idata = Signal(intbv(0, min=0, max=depth))
            idata_next = Signal(intbv(0, min=0, max=depth))
            odata = Signal(intbv(0, min=0, max=depth))
            odata_sample = Signal(intbv(0, min=0, max=depth))
            push  = Signal(intbv(0)[1:0])
            pop   = Signal(intbv(0)[1:0])
            # the literally full signal (usedboard controlled)
            full  = Signal(intbv(0)[1:0])
            # the intensity phase control full signal
            full_hyst = Signal(intbv(0)[1:0])
            # the literally empty signal (num_free controlled)
            empty = Signal(intbv(0)[1:0])
            # the intensity phase control empty signal
            empty_hyst = Signal(intbv(0)[1:0])
            num_free = Signal(intbv(0, min=0, max=depth+1))
            consistency_check  = Signal(intbv(0)[1:0])
            error  = None

            usedboard = []
            ub_len = Signal(intbv(0, min=0, max=depth+1))
            freeboard = list(range(depth))

            pre_push = Signal(intbv(0)[1:0])
            push_rand = Signal(intbv(0)[1:0])
            pre_pop = Signal(intbv(0)[1:0])
            pop_rand = Signal(intbv(0)[1:0])

            full_count = Signal(intbv(0))
            empty_count  = Signal(intbv(0))
            clk_count = Signal(intbv(0))
            clk_count_limit = Signal(intbv(0))

            # Probabilities for push and pop
            prob_max = 32
            prob_high = random.randrange(prob_max//4, prob_max)
            prob_low = prob_high//2
            prob_full = random.randrange(prob_max//8, prob_max)
            prob_empty = random.randrange(prob_max//8, prob_max)
            prob_push = Signal(intbv(0, max=prob_max))
            prob_pop  = Signal(intbv(0, max=prob_max))
            prob_phase = Signal(modbv(0, min=0, max=4))
            flush_phase = Signal(intbv(0)[1:0])
            flush_finished = Signal(intbv(0)[1:0])
            flat_cycles = max(200, 5 * depth)

            @always_comb
            def set_full():
                # need hysteresis to avoid bounces when counting
                if rstn==1:
                    if ub_len == 0:
                        if full_log:
                            print('full/full_hyst to 1 at ', time_step*sim_time)
                            sys.stdout.flush
                        full.next = 1
                        if prob_phase == 2:
                            full_hyst.next = 1
                    elif ub_len < 6*depth//8:
                        if full_log:
                            print('full to 0 at ', time_step*sim_time)
                            sys.stdout.flush()
                        full.next = 0
                    else:
                        # ub_len >= 6*depth/8:
                        if full_log:
                            print('full_hyst to 0 at ', time_step*sim_time)
                            sys.stdout.flush()
                        full.next = 0
                        full_hyst.next = 0
                else:
                    # free starts full
                    full.next = 1
                    full_hyst.next = 1
                    
            @always_comb
            def set_empty():
                # need hysteresis to avoid bounces when counting
                if rstn==1:
                    if num_free==0:
                        if empty_log:
                            print('empty/empty_hyst to 1 at ',\
                                time_step*sim_time)
                            sys.stdout.flush()
                        empty.next = 1
                        if prob_phase == 0:
                            empty_hyst.next = 1
                    elif 0 < num_free <= 6*depth//8:
                        if empty_log:
                            print('empty to 0 at ', time_step*sim_time)
                            sys.stdout.flush()
                        empty.next = 0
                    else:
                        # num_free > 6*depth/8:
                        if empty_log:
                            print('empty_hyst to 0 at ', time_step*sim_time)
                            sys.stdout.flush()
                        empty.next = 0
                        empty_hyst.next = 0
                else:
                   empty.next = 0
                   empty_hyst.next = 0


            # print to log makes it somewhat simpler to repeat
            print('Stimuli Prob; ', end=' ')
            print('high:', prob_high, end=' ')
            print(' low:', prob_low, end=' ')
            print(' full:', prob_full, end=' ')
            print(' empty:', prob_empty, '(', prob_max, ')')
            sys.stdout.flush()

            # If we've become full more times than we've become empty
            # set a higher pop probability (and vice versa)
            @always_comb
            def set_prob():
                if prob_phase == 0:
                    # purge
                    prob_push.next = prob_low
                    prob_pop.next = prob_high
                elif prob_phase == 1:
                    # hover at empty
                    prob_push.next = prob_empty - 1
                    prob_pop.next = prob_empty
                elif prob_phase == 2:
                    # fill'er up
                    prob_push.next = prob_high
                    prob_pop.next  = prob_low
                else:
                    # prob_phase == 3
                    # hover at full
                    prob_push.next = prob_full
                    prob_pop.next  = prob_full - 1

                if prob_log==1:
                    if flush_phase==0:
                        print('prob_phase ', prob_phase,\
                            ' push:', prob_push.next,\
                            ' pop:', prob_pop.next, end=' ')
                    else:
                        print('flush_phase', end=' ')
                    print(' at: ', time_step*sim_time)
                    sys.stdout.flush()

            # Count the number of times we've become full
            @always(full_hyst.posedge)
            def count_full():
                if rstn == 0:
                    full_count.next = 0
                else:
                    if prob_log==1:
                        print('full_hyst posedge at ', time_step*sim_time)
                    sys.stdout.flush()
                    if prob_phase == 2:
                        prob_phase.next = prob_phase + 1
                        clk_count_limit.next = clk_count + flat_cycles
                        full_count.next += 1
                        if prob_log==1:
                            print('prob_phase transition 2->3')
                        else:
                            if full_count==1:
                                print('Cycles:')
                            print('{0:3d}'.format(0+full_count), end=' ')
                            if (full_count)%20 == 0:
                                print()
                        sys.stdout.flush()

            # Count the number of times we've become empty
            @always(empty_hyst.posedge)
            def count_empty():
                if rstn == 0:
                    empty_count.next = 0
                else:
                    if prob_log==1:
                        print('empty_hyst posedge at ', time_step*sim_time,\
                            'phase:', prob_phase)
                    if prob_phase == 0:
                        clk_count_limit.next = clk_count + flat_cycles
                        empty_count.next += 1
                        if(empty_count==nr):
                            flush_phase.next = 1
                        else:
                            prob_phase.next = prob_phase + 1
                            if prob_log==1:
                                print('prob_phase transition 0->1')
                                sys.stdout.flush()

            @always_comb
            def pre_push_gen():
                if full==0 and clk_count>0: 
                    pre_push.next = push_rand
                else:
                    pre_push.next = 0

            # delay push to neg edge
            @always(clk.negedge, rstn.negedge)
            def push_later():
                if rstn==0:
                    push.next = 0
                else:
                    push.next = pre_push

            @always_comb
            def pre_pop_gen():
                if empty==0:
                    pre_pop.next = pop_rand
                else:
                    pre_pop.next = 0

            # delay pop to neg edge
            @always(clk.negedge, rstn.negedge)
            def pop_later():
                if rstn==0:
                    pop.next = 0
                else:
                    pop.next = pre_pop

            # Toggle push and pop according to the probabilities
            @always(clk.posedge, rstn.negedge)
            def random_push_pop():
                if rstn==1:
                    if flush_phase==0:
                        push_rand.next = random.randrange(prob_max)<=prob_push
                        pop_rand.next = random.randrange(prob_max)<=prob_pop
                    else:
                        push_rand.next = 0
                        pop_rand.next = 1

            # Find and return a random used address
            def push_value(index=0):
                # called on falling edge
                self.assertEqual(
                    ub_len>0, True,
                    msg='no addresses to free')
                index = random.randrange(ub_len)
                val = usedboard[index]
                freeboard.append(val)
                usedboard.pop(index)
                return val

            def pop_value(val):
                # called on rising edge
                self.assertEqual(
                    val in freeboard, True,
                    msg='odata[]=' + repr(val) + ' (0x{0:X})'.format(val)
                    + ' is not free, '
                    + 'len(freeboard)= %d ' % len(freeboard)
                    + '  freeboard: ' + str(freeboard)
                )
                usedboard.append(val)
                freeboard[:] = [v for v in freeboard if v != val]
                
            @always(clk.negedge)
            def clk_counter():
                if rstn==0:
                    clk_count.next = 0
                else:
                    clk_count.next = clk_count + 1
                    if (clk_count+1) == clk_count_limit:
                    # if clk_count.next == clk_count_limit:
                        if flush_phase==1:
                            flush_finished.next = 1
                        else:
                            # hover phase finished
                            prob_phase.next = prob_phase + 1
                            if prob_log:
                                print('clk_count_limit reached at ',\
                                       time_step*sim_time)
                                sys.stdout.flush()

            # pushed free data was popped from usedboard
            @always(clk.negedge)
            def data():
                if rstn==1:
                    if pre_push==1:
                        if pp_log:
                            print('push data available at ',\
                                   time_step*sim_time)
                            sys.stdout.flush()
                        val = push_value()
                        idata.next = val

            # sample odata earlier
            @always(clk.negedge)
            def odata_sampler():
                odata_sample.next = odata

            # popped free data is pushed to the usedboard
            @always(clk.posedge)
            def driver():
                if rstn==1:
                    if pre_pop==1:
                        if pp_log:
                            print('pop samples at ', time_step*sim_time)
                            sys.stdout.flush()
                        pop_value(value(odata_sample))
                ub_len.next = len(usedboard)

            # After emptying free, compare range with the usedboard
            @always(clk.posedge)
            def stop_simulation():
                if flush_finished==1:
                    self.assertEqual(len(freeboard), 0)
                    self.assertEqual(num_free, 0)
                    self.assertEqual(sorted(usedboard), list(range(depth)))

                    # option to deliberately cause assertion violation
                    self.assertTrue(True)

                    raise StopSimulation 

            # Here we create the DUT and generate the RTL (if necessary)
            dut = self.createDUT(mod_name, block_name, postfix, cosim, synt,
                                 ['i', 'o', 'i', 'i',
                                  'o', 'i', 'i', 'i', 'o', 
                                  'v', 'v', 'v'], module,
                                 idata, odata, push, pop,
                                 num_free, consistency_check, clk, rstn, error, 
                                 depth, fm_width, mode)
            return instances()
        ### End of tb ###
        
        ### run_test_free continues ###

        # control of the hw generation and nr stimuli cycles
        modes = ['default', 'matrix', 'lifo', 'lifo_3cc', 'fifo']
        selector = 0 

        if selector == 0:
            # Randomize several hardware configurations

            number_of_stimuli_cycles = 10
            number_of_configurations = 20
 
            min_fm_width_power = 4 #2**4=16
            max_fm_width_power = 8 #2**(8-1)=128
            fm_widths = [
                2**random.randrange(min_fm_width_power, max_fm_width_power)
                for _ in range(number_of_configurations)
            ]
        
            min_depth = 8
            max_depth = 255
            depths = random.sample(range(min_depth, max_depth+1),
                               number_of_configurations-2)
            depths.append(17)
            depths.append(256)

            # adjust fm_width to ensure a memory with at least 2 rows
            adj_fm_widths = []
            for d, f in zip(depths, fm_widths):
                adj_fm_widths.append( min(f, 2**((d-1).bit_length()-1)))

            # print '(depth, fm_width): ', str(zip(depths, adj_fm_widths))

        elif selector == 1:
            # a very small one
            adj_fm_widths = [16]
            depths = [17]
            number_of_stimuli_cycles = 100

        elif selector == 2:
            # slightly larger
            adj_fm_widths = [16]
            depths = [55]
            number_of_stimuli_cycles = 100

        elif selector == 3:
            # target size for cavium design
            adj_fm_widths = [128]
            depths = [6554]
            number_of_stimuli_cycles = 100
        else:
            # error
            print('error test_free variable selector not configured right')
            sys.stdout.flush()
            
        for d, f in zip(depths, adj_fm_widths):
            for m in modes:
                # Simulate the hardware configuration
                self.runSimulation(
                    # do not use any parameter names here!!
                    # only provide the arguments in the right places
                    testbench, mod_name, block_name,
                    '_d'+str(d)+'_w'+str(f)+"_"+m,
                    d, f, m, number_of_stimuli_cycles)

# This is needed for automatically running the unit tests
if __name__ == '__main__':
    unittest.main()
