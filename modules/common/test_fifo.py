from myhdl import *
from random import sample, randrange, randint, uniform
from math import ceil
import unittest
from unittesting.ClockedTestCase import ClockedTestCase, listType
from collections import deque
from .fifo_imp import fifo_imp
from .lifo import lifo
from .fifo_async import fifo_async
from .Common import value, copySignal, signalType

# 72 and 79 characters
# 345678_112345678_212345678_312345678_412345678_512345678_612345678_712 456789

class UnitTest(unittest.TestCase, ClockedTestCase):
    def setUp(self):
        super(UnitTest, self).setUpSeed()

    def test_fifo_long(self):
        mod_name = 'fifo_imp'
        block_name = 'fifo_imp'
        module = fifo_imp
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=False, loops=2000)
        
    def test_fifo(self):
        mod_name = 'fifo_imp'
        block_name = 'fifo_imp'
        module = fifo_imp
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=False)

    def test_lifo_long(self):
        mod_name = 'lifo'
        block_name = 'lifo'
        module = lifo
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=False, loops=500)

    def test_lifo(self):
        mod_name = 'lifo'
        block_name = 'lifo'
        module = lifo
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=False)

    def test_fifo_async_long(self):
        mod_name = 'fifo_async'
        block_name = 'fifo_async'
        module = fifo_async
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=True, loops=200)

    def test_fifo_async(self):
        mod_name = 'fifo_async'
        block_name = 'fifo_async'
        module = fifo_async
        self.run_test_fifo_or_lifo(mod_name, block_name, module, is_async=True)

    def run_test_fifo_or_lifo(self, mod_name, block_name, module, is_async=False, loops=5):
        # The testbench needs to have the parameters cosim and synt,
        # and they have to be set as false by default
        # It needs to be named testbench
        mod_name = f"modules.common.{mod_name}"
        def testbench(
                mod_name, block_name, postfix, width=16, depth=5,
                memory_mode='ff', memory_input_flops=0, memory_output_flops=0, is_async=False,
                throughput_upper=50, throughput_lower=33,
                throughput_margin=5, nr=5,
                cosim=False, synt=False):

            # Declare clock and reset
            clk = Signal(intbv(0)[1:0])
            rstn = Signal(intbv(0)[1:0])
            clear = Signal(intbv(0)[1:0])
            t_clk = 10
            clk_cnt = Signal(intbv(0))

            if is_async==True:
                # TODO: Make the testbench work with max_ratio > 1.0
                max_ratio = 1.0
                if max_ratio != 1:
                    t_oclk = randrange(
                        int(t_clk/max_ratio), ceil(t_clk*max_ratio))
                else:
                    t_oclk = t_clk
                print("Clock ratio = ", t_clk/float(t_oclk))
                oclk  = Signal(intbv(0)[1:0]) 
                orstn = Signal(intbv(0)[1:0])
                @always(delay(t_oclk))
                def oclkgen():
                    oclk.next = not oclk
                @instance
                def orstngen():
                    orstn.next = 0
                    yield delay(100*t_oclk)
                    yield oclk.posedge
                    orstn.next = 1

            # Generate clock and reset
            @instance
            def rstngen():
                rstn.next = 0
                yield delay(100*t_clk)
                yield clk.posedge
                rstn.next = 1

            @always(delay(t_clk))
            def clkgen():
                clk.next = not clk

            iclk=clk
            irstn=rstn
            if is_async==False:
                oclk=clk

            clear_is_tested = (randrange(0, 2)==1)
            if is_async==True:
                clear_is_tested = False
            if block_name == 'lifo':
                clear_is_tested = False
            if block_name == 'fifo_imp' and memory_mode == 'mem' and memory_input_flops+memory_output_flops>0:
                clear_is_tested = False

            clear_start_clk_cnt = 100
            clear_stop_clk_cnt = clear_start_clk_cnt + randrange(1, 5)

            @always(clk.posedge, rstn.negedge)
            def clearGen():
                clear.next = 0
                if (rstn
                    and clear_is_tested
                    and clk_cnt>=clear_start_clk_cnt
                    and clk_cnt<clear_stop_clk_cnt
                ):
                    clear.next = 1

            # Check if width is a list
            list_mode = listType(width)
            # Declare the rest of the signals
            if list_mode:
                list_widths = width
                idata = [Signal(intbv(0)[x:]) for x in list_widths]
                odata = [Signal(intbv(0)[x:]) for x in list_widths]
            else:
                idata = Signal(intbv(0)[width:])
                odata = Signal(intbv(0)[width:])
            push  = Signal(intbv(0)[1:0]) 
            pop   = Signal(intbv(0)[1:0]) 
            full  = Signal(intbv(0)[1:0]) 
            almost_full  = Signal(intbv(0)[1:0])
            empty = Signal(intbv(0)[1:0]) 
            almost_empty = Signal(intbv(0)[1:0]) 

            # get cosim conversion error message that a modbv
            # object should have full bit vector range
            _level = Signal(modbv(0, min=0, max=depth+1))
            level = Signal(modbv(0, min=0, max=2**len(_level)))
            # level = Signal(intbv(0,min=0,max=depth+1))

            level_d = Signal(intbv(0, min=0, max=depth+1))
                #value in previous clock cycle
            scoreboard = deque()
            result = deque()

            push_rand = Signal(intbv(0)[1:0])
            pop_rand = Signal(intbv(0)[1:0])
            
            last_increment_level_is_0_not_full = Signal(intbv(1))
                # last event was beginning of level==0 burst
            full_cnt = Signal(intbv(0))
            level_is_0_cnt = Signal(intbv(0))
            push_cnt = Signal(intbv(0))
            pop_cnt = Signal(intbv(0))
            
            # Probablilties for push and pop,
            # probability(true) = throughput_x/throughput_sample_space
            throughput_sample_space = Signal(intbv(100))
            throughput_push = Signal(intbv(100))
            throughput_pop  = Signal(intbv(100))

            # switch between filling and emptying depending on the beginning
            # of bursts of level=0 and the signal full
            @always_comb
            def setThroughput():
                if last_increment_level_is_0_not_full == 0:
                    # pop more
                    throughput_push.next = throughput_lower
                    throughput_pop.next = throughput_upper
                else:
                    # push more
                    throughput_push.next = throughput_upper
                    throughput_pop.next  = throughput_lower

            # Count the number of times we've become full
            @always(full.posedge)
            def countFull():
                if rstn == 0:
                    full_cnt.next = 0
                else:
                    if last_increment_level_is_0_not_full != 0:
                        full_cnt.next += 1
                        last_increment_level_is_0_not_full.next = 0

            # Count the number of times we've become level=0
            # Note that the empty signal in the case of mem3
            # is not the same as beeing really empty and level=0
            # instead empty signal is hiding internal latencies
            @always(clk.posedge)
            def countLevelIs0():
                if rstn == 0:
                    level_is_0_cnt.next = 1
                else:
                    if level == 0 and level_d == 1:
                        if last_increment_level_is_0_not_full != 1:
                            level_is_0_cnt.next += 1
                            last_increment_level_is_0_not_full.next = 1

            @always(clk.posedge)
            def levelDFf():
                if rstn == 0:
                    level_d.next = 0
                else:
                    if clear==1:
                        level_d.next = 0
                    else:
                        level_d.next = level
                    
            # Count the number of cycles
            @always(clk.posedge)
            def countClk():
                if rstn == 0:
                    clk_cnt.next = 0
                else:
                    clk_cnt.next += 1
                    
            # Count the number of cycles there were a push
            @always(clk.posedge)
            def countPush():
                if rstn == 0:
                    push_cnt.next = 0
                else:
                    if push == 1:
                        push_cnt.next += 1

            # Count the number of cycles there were a pop
            @always(clk.posedge)
            def countPop():
                if rstn == 0:
                    pop_cnt.next = 0
                else:
                    if pop == 1:
                        pop_cnt.next += 1
                    
            # Toggle push and pop according to the probabilities
            @always(clk.posedge, rstn.negedge)
            def randomize():
                push_rand.next = 0
                pop_rand.next = 0
                if rstn==1 and clear==0:
                    push_rand.next = (
                        randrange(throughput_sample_space) < throughput_push)
                    pop_rand.next = (
                        randrange(throughput_sample_space) < throughput_pop)

            @always_comb
            def pushGen():
                push.next = push_rand and not full

            @always_comb
            def popGen():
                pop.next = (pop_rand==1) and (empty==0)

            # Generate the data
            def dataGenerator(index=0):
                if list_mode:
                    return randrange(2**list_widths[index])
                else:
                    return randrange(2**width)

            if list_mode:
                @always(clk.posedge, rstn.negedge)
                def createData():
                    if rstn and push:
                        for x in range(len(idata)):
                            idata[x].next = dataGenerator(x)
            else:
                @always(clk.posedge, rstn.negedge)
                def createData():
                    if rstn:
                        idata.next = dataGenerator()

            if signalType(idata):
                scoreboard_out = copySignal(idata)
                @always(clk.negedge)
                def so():
                    if len(scoreboard) > 0:
                        scoreboard_out.next = scoreboard[-1]
                    else:
                        scoreboard_out.next = 0
                    
            # Push the generated data to the scoreboard
            @always(clk.posedge)
            def driver():
                if rstn==0 or clear==1:
                    scoreboard.clear()
                else:
                    if block_name == 'fifo_imp' or block_name == 'fifo_async':
                        if push:
                            #print "Pushing %s to scoreboard" % value(idata)
                            scoreboard.append(value(idata))
                    elif block_name == 'lifo':
                        if push:
                            #print "Pushing %s to scoreboard" % value(idata)
                            scoreboard.append(value(idata))
            operations = Signal(intbv(0)[64:])
            if block_name == 'fifo_imp' or block_name == 'fifo_async':
                first = Signal(modbv(0)[1:])
                # Empty the queue and compare with the scoreboard
                @always(oclk.posedge)
                def receiver():
                    if rstn==0 or clear==1:
                        result.clear()
                        first.next = 1
                        operations.next = 0
                    else:
                        if block_name == 'fifo_imp':
                            if empty==0:
                                first.next = 0
                                assert level>0
                            else:
                                assert level==0
                        if pop:
                            result.append(value(odata))
                            if block_name == 'fifo_imp':
                                if full:
                                    self.assertEqual(level+0, depth)
                                else:
                                    self.assertNotEqual(level+0, depth)

                            # make sure that level values are not
                            # changing more than 1 for each clk cycle
                            level_xr = range(
                                max(0, level_d-1), min(depth+1, level_d+2))
                            if first==0:
                                self.assertIn(level, level_xr)
                        dlen = min(len(result), len(scoreboard))
                        if dlen>0:
                            operations.next += dlen
                            for i in range(dlen):
                                if result[0] != scoreboard[0]:
                                    print("ERROR! Expected %s, but got %s" % (hex(scoreboard[0]), hex(result[0]))) 
                                    print("Scoreboard")
                                    for i in range(len(scoreboard)):
                                        print(hex(scoreboard[i]))
                                    print()
                                    print("Result")
                                    for i in range(len(result)):
                                        print(hex(result[i]))
                                    
                                    assert False
                                result.popleft()
                                scoreboard.popleft()
                            
                                
                        if full_cnt >= nr and level_is_0_cnt >= nr:
                            print("Stopping after", full_cnt, "full and", level_is_0_cnt, "level==0.", operations, "operations")
                            for _ in range(len(result)):
                                if False:
                                    print('r', result[0], 's', scoreboard[0])
                                self.assertEqual(result[0], scoreboard[0])
                                result.popleft()
                                scoreboard.popleft()

                            if (False and
                                (
                                    (100. * throughput_lower
                                     / throughput_sample_space
                                     >
                                     100. * push_cnt/clk_cnt )
                                 or (100. * push_cnt/clk_cnt
                                     >
                                     100. * throughput_upper
                                     / throughput_sample_space)
                                 or (100. * throughput_lower
                                     / throughput_sample_space
                                     >
                                     100. * pop_cnt/clk_cnt )
                                 or (100. * push_cnt/clk_cnt
                                     >
                                     100. * throughput_upper
                                     /throughput_sample_space)
                                )
                            ):
                                print((
                                    "Throughput mod_name:{} block_name:{} "
                                    + "module:{} memory_mode:{} width={} "
                                    +"depth={}"
                                ).format(
                                    mod_name, block_name, module,
                                    memory_mode, width, depth))
                                print((
                                    "Throughput Low Limit Push: {0:.10f}% "
                                    + "Pop: {1:.10f}%"
                                ).format(
                                    100. * throughput_lower
                                    / throughput_sample_space,
                                    100. * throughput_lower
                                    / throughput_sample_space))
                                print((
                                    "Throughput Measured  Push: {0:.10f}% "
                                    + "Pop: {1:.10f}%"
                                ).format(
                                    100. * push_cnt/clkCnt,  100. * pop_cnt
                                    / clkCnt))
                                print((
                                    "Throughput HighLimit Push: {0:.10f}% "
                                    + "Pop: {1:.10f}%"
                                ).format(
                                    100. * throughput_upper
                                    / throughput_sample_space,
                                    100. * throughput_upper
                                    / throughput_sample_space))

                            # check throughput only when not asychronous
                            if is_async==False:
                                self.assertGreater(
                                    100. * push_cnt / clk_cnt,
                                    100. * (throughput_lower
                                            - throughput_margin)
                                    / throughput_sample_space)
                                self.assertGreater(
                                    100. * throughput_upper
                                    / throughput_sample_space,
                                    100. * push_cnt/clk_cnt)
                                self.assertGreater(
                                    100. * pop_cnt/clk_cnt,
                                    100. * (throughput_lower
                                            - throughput_margin)
                                    / throughput_sample_space)
                                self.assertGreater(
                                    100. * throughput_upper
                                    /throughput_sample_space,
                                    100. * pop_cnt/clk_cnt)

                            raise StopSimulation
            elif block_name == 'lifo':
                # Empty the queue and compare with the scoreboard
                @always(clk.negedge)
                def receiver():
                    if pop and rstn:
                        if scoreboard[-1] != value(odata):
                            print("Mismatch! Expected %s got %s" %(hex(scoreboard[-1]), hex( value(odata))))
                            self.assertEqual(0, 1)
                        scoreboard.pop()
                    if full_cnt >= nr and level_is_0_cnt >= nr:
                        raise StopSimulation 
            else:
                print("Unsupported block", block_name)
                exit()

            # Here we create the DUT and generate the RTL (if necessary)
            if is_async==True:
                empty_margin = "default"
                full_margin  = "default"
                dut = self.createDUT(
                    mod_name, block_name, postfix,
                    cosim, synt,
                    ['i', 'o', 'i', 'i',
                     'o', 'o', 'o', 'o',
                     'o', 'i', 'i', 'i', 'i',
                     'v', 'v', 'v', 'v',
                     'v'],
                    module,
                    idata, odata, push, pop,
                    full, almost_full, empty, almost_empty,
                    level, iclk, oclk, irstn, orstn,
                    depth, empty_margin, full_margin,  1,
                    memory_mode
                )
            else:
                dut = self.createDUT(
                    mod_name, block_name, postfix,
                    cosim, synt,
                    [ 'i', 'o', 'i', 'i',
                      'o', 'o', 'o', 'i',
                      'i', 'v', 'v', 'v',
                      'v', 'v', 'v'],
                    module,
                    idata, odata, push, pop,
                    full, empty, level, clk,
                    rstn, clear if memory_mode is not "mem3" else 0,  depth,  1,
                    memory_mode, memory_input_flops, memory_output_flops
                )

            return instances()
        ### End of tb ###
        
        ### run_test_fifo_or_lifo continues ###

        ###
        # Random hardware configuration

        list_modes = [False, True]
        if is_async:
            memory_modes = ['mem']
        elif block_name == 'fifo_imp':
            memory_modes = ['mem', "ff"]# , 'mem+ff', 'mem3'] #
        else:
            memory_modes = ['ff', 'mem', 'mem+ff']
            
        # All permutations of list_mode and MemoryMode
        from itertools import product
        mode_list = list(product(list_modes, memory_modes))

        widths = sample(range(2, 33), len(mode_list*2))
        #widths.append(1)
        if is_async:
            depths=[]
            depths_W = sample(range(4, 10), len(mode_list*2))
            for i in depths_W:
                depths.append(2**i)
            #depths.append(4)
        else:
            #population needs to be larger than the number of unique samples
            depths = sample(
                range(16, len(mode_list*2)+20), len(mode_list*2))
            #depths.append(4)
                #use a 1 here instead of 4 to trigger a throughput assertion
            
        ###
        # Random stimuli characteristics

        # different throughputs
        throughput_min = 25
        throughput_max = 100
        throughput_absolute_difference = 10
            # need some difference to get reasonable execution times
        throughput_relative_difference = 25
            # need some difference to get reasonable execution times
        throughput_margin = 5
            # to decrease the lower threshold to avoid false throughput errors
        throughput0_list = sample(
            range(throughput_min, throughput_max),
            2 * len(mode_list))
        throughput1_list = sample(
            range(throughput_min, throughput_max),
            2 * len(mode_list))

        ###
        # Exit criteria
        
        # The test will stop when the fifo has become full and levelIs0
        # this number of times
        nr_of_full_level_is_0 = loops

        ###
        # go through test scenarios
        for lm, memory_mode in mode_list*2:            
            memory_input_flops  = randrange(2)
            memory_output_flops = randrange(2)
            if (block_name=="lifo"):
                if memory_mode=="mem+ff":
                    memory_input_flops=1
                    memory_output_flops=1
                else:
                    memory_input_flops=0
                    memory_output_flops=0
                    
            w = widths.pop()
            d = depths.pop()
            t0 = throughput0_list.pop()
            t1 = throughput1_list.pop()
            throughput = sorted([t0, t1])
            throughput_upper = max(throughput[1], throughput[0])
            throughput_lower = min(
                throughput[1],
                throughput[0],
                throughput_upper-throughput_absolute_difference,
                throughput_upper*(100-throughput_relative_difference)//100)

            if lm:
                wdata = sample(range(1, 13), randint(1, 6))
            else:
                wdata = w
            wstring = str(wdata).replace(" ", "").replace(",", "_").replace(
                "[", "").replace("]", "")

            # Simulate the hardware configuration
            self.runSimulation(
                testbench, mod_name, block_name,
                ('_w' + wstring + "_d" + str(d) + '_lm' + str(int(lm))
                 + '_' + memory_mode + '_mf' + str(memory_input_flops)+str(memory_output_flops)+'_tu' + str(throughput_upper)
                 + '_tl' + str(throughput_lower)),
                wdata, d, memory_mode, memory_input_flops, memory_output_flops, is_async,
                throughput_upper, throughput_lower,
                throughput_margin, nr_of_full_level_is_0)

# initiate these unit tests only if this file is the main python file
if __name__ == '__main__':
    unittest.main()
