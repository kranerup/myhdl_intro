from collections import deque
import unittest
from myhdl import *
from unittesting.ClockedTestCase import *
from .min_max_buckets import min_max_buckets
from random import randrange, sample, randint
from copy import copy

class UnitTest(unittest.TestCase, ClockedTestCase):

    def setUp(self):
        super(UnitTest, self).setUpSeed()
       
    def test_min_max_buckets(self):
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        # It needs to be named tb_{blockName}
        def testbench(modName, blockName, postfix, nr_of_queues, max_pkt, core_freq, bw_width, max_bw, min_bw, max_burst, nr=100, cosim=False, synt=False):

            print("Running", modName, blockName, postfix, nr_of_queues, max_pkt, core_freq, max_bw, min_bw, max_burst, nr, cosim, synt)
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

            @instance
            def addr_gen():
                yield clk.posedge
                if readCnt >= nr:
                    yield clk.posedge
                    raise StopSimulation    
                        
            @always(clk.posedge)
            def compare():
                if rstn==0:
                    readCnt.next = 0
                else:
                    readCnt.next += 1
            #        self.assertEqual(reset_value, value(odata))
            
            
            available       = Signal(intbv(0)[nr_of_queues:0])
            allowed         = copySignal(available)
            queue           = Signal(intbv(0, min=0, max=nr_of_queues))
            valid_bytes     = Signal(intbv(0, min=0, max=max_pkt+1))
            sig_min_bw      = [Signal(intbv(0))[bw_width:] for _ in range(nr_of_queues)]
            sig_max_bw      = [Signal(intbv(0))[bw_width:] for _ in range(nr_of_queues)]
            sig_max_burst   = [Signal(intbv(0))[bw_width:] for _ in range(nr_of_queues)]

#            dut = self.createDUT(modName, blockName, postfix, cosim, synt, 
#                                 ['i',     'o',     'i',   'i',         'i',    'i',    'i',       'i', 'i',  'v',       'v'], min_max_buckets,
#                                 available, allowed, queue, valid_bytes, min_bw, max_bw, max_burst, clk, rstn, core_freq, max_pkt)
            return instances()
#
#        number_of_configurations = 3
#        max_nr_of_queues = 16
#        max_max_pkt      = 32000
#        min_max_pkt      = 1500
#        min_core_freq    = 10
#        max_core_freq    = 600
#        min_bw_width     = 12
#        max_bw_width     = 64
#        # Test signalmode
#        queues    = random.sample(xrange(1,max_nr_of_queues),          number_of_configurations)
#        max_pkt   = random.sample(xrange(min_max_pkt,max_max_pkt),     number_of_configurations)
#        core_freq = random.sample(xrange(min_core_freq,max_core_freq), number_of_configurations)
#        bw_width  = random.sample(xrange(min_bw_width,max_bw_width),   number_of_configurations)
#        max_bw = []
#        min_bw = []
#        max_burst = []
#        for i in range(nr_of_configurations):
#            max_bw  = random.sample(xrange(1,(1<<bw_width[i])-1), queues[i])
#        for i in range(nr_of_configurations):
#            for q in range(queues[i]):
#                min_bw.append( random.randrange(1,max_bw[i][q]) )
#        for i in range(nr_of_configurations):
#            max_burst = random.sample(xrange(1,(1<<bw_width[i])-1), queues[i])
#
#        for q, mp, cf, bw, mab, mib, mbu in zip(queues, max_pkt, core_freq, bw_width, max_bw, min_bw, max_burst):
#            mabstring = str(mab).replace(" ", "").replace(",","_").replace("[","").replace("]","")
#            mibstring = str(mib).replace(" ", "").replace(",","_").replace("[","").replace("]","")
#            mbustring = str(mbu).replace(" ", "").replace(",","_").replace("[","").replace("]","")
        q = 3
        mp = 1500
        cf = 75
        bw = 16
        mab = [7, 8, 9]
        mib = [1, 2, 3]
        mbu = [1000, 1000, 1000]
        self.runSimulation(testbench, "modules.common.min_max_buckets", 'min_max_buckets', '_maxbw'+mabstring+'_minbw'+str(mibstring)+"_maxburst"+str(mbustring), q, mp, cf, bw, mab, mib, mbu)
                
               
if __name__ == '__main__':
    unittest.main()
