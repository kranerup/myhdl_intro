from collections import deque
import unittest
from myhdl import *
from unittesting.ClockedTestCase import *
from .Common import value, multiflop_e
from .mempipe import mempipe
from random import randrange, sample, randint
from copy import copy

class UnitTest(unittest.TestCase, ClockedTestCase):

    def setUp(self):
        super(UnitTest, self).setUpSeed()
       
    def test_mempipe(self):
        self.run_test_mempipe()

    def run_test_mempipe(self):
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        # It needs to be named tb_{blockName}
        def testbench(modName, blockName, postfix, width, depth, input_flops, output_flops, nr=10000, cosim=False, synt=False):

            print("Running", modName, blockName, postfix, width, depth, nr, cosim, synt)
            clk = Signal(intbv(0)[1:0])
            rstn = Signal(intbv(0)[1:0])

            @instance
            def rstngen():
                rstn.next = 0
                yield delay(100)
                rstn.next = 1

            @always(delay(10))
            def clkgen():
                clk.next = not clk

            iclk = clk
            oclk = clk

            idata = Signal(intbv(0)[width:])
            last_idata = Signal(intbv(0)[width:])
            odata = Signal(intbv(0)[width:])
            enable = Signal(intbv(0)[1:])
            enable_ff = Signal(intbv(0)[1:])
  
            iPipei = multiflop_e(idata, last_idata, enable, clk, rstn, depth=depth)
          
            # Generate the data
            def dataGenerator(index=0):
                return randrange(2**len(idata))

            module = mempipe
            dut = self.createDUT(modName, blockName, postfix, cosim, synt, 
                                 ['i',   'o',   'i',    'i',   'i',  'v',   'v',         'v',  ], module,
                                 idata,  odata, enable, clk,   rstn, depth, input_flops, output_flops)
            readCnt = Signal(intbv(0))
            
            @instance
            def data_gen():
                yield clk.posedge
                enable.next = 0
                while not rstn:
                    yield clk.posedge
                while True:
                    yield clk.negedge
                    write = randrange(2)==0
                    val = randrange(2**(len(idata)))
                    idata.next = val
                    if input_flops+output_flops>0:
                        enable.next = 1
                    else:
                        enable.next = write
                    if readCnt >= nr+depth:
                        yield clk.posedge
                        raise StopSimulation    
                        
            @always(clk.posedge)
            def compare():
                if rstn==0:
                    readCnt.next = 0
                    enable_ff.next = 0
                else:
                    enable_ff.next = enable
                    readCnt.next += 1
                    # The memory will output X when it is not read, so we cannot compare it right after we have had enable low
                    # But enable is only meant to be used for stalling the pipeline when it is empty, so this case is fine.
                    if enable_ff==1 and readCnt>=depth:  
                        self.assertEqual(value(last_idata), value(odata))
            return instances()

        number_of_configurations = 10
        max_signal_width = max(number_of_configurations, 160)
        min_signal_width = max(number_of_configurations, 4)
        max_depth = max(number_of_configurations*2, 130)
        min_depth = max(number_of_configurations, 4)
        flops = [0, 1]
        modName = 'modules.common.mempipe'
        blockName = 'mempipe'
        
        widths = random.sample(range(min_signal_width, max_signal_width), number_of_configurations)
        depths = random.sample(range(min_depth, max_depth), len(widths))
        iflops = [ random.choice(flops) for _ in range(len(widths)) ]
        oflops = [ random.choice(flops) for _ in range(len(widths)) ]
        for w, d, iflop, oflop in zip(widths, depths, iflops, oflops):
            self.runSimulation(testbench, modName, blockName, '_w'+str(w)+'_d'+str(d)+'_if'+str(iflop)+'_of'+str(oflop), w, d, iflop, oflop)
               
if __name__ == '__main__':
    unittest.main()
