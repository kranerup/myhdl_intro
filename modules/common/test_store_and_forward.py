import unittest
from myhdl import *
from unittesting.ClockedTestCase import *
from .Common import value, pass_through
from random import randrange, sample
from modules.interface.RawDataPacket import *
from .store_and_forward import store_and_forward 
from collections import deque

class UnitTest(unittest.TestCase, ClockedTestCase):

    def setUp(self):
        super(UnitTest, self).setUpSeed()
       
    def test_store_and_forward(self):
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        def testbench(modName, blockName, postfix, width, depth, speed_fraction=1.0, nr=10, cosim=False, synt=False):

            print("Running", modName, blockName, postfix, width, depth, speed_fraction, nr)
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

            inIf        = []
            outIf       = []
            inIf_logic  = []
            driver_logic   = []
            outIf_logic    = []
            receiver_logic = []
            tbInSig        = []
            tbOutSig       = []
            halt = Signal(intbv(0)[1:0])
            chaos_done = Signal(intbv(0)[1:0])
            for w, s in zip(width, speed_fraction):
                inIf.append(  RawDataPacketInterface("inIf",  halt, clk, rstn, busWidth=w, speed_fraction=s, chaos_done=chaos_done))
                outIf.append( RawDataPacketInterface("outIf", halt, clk, rstn, busWidth=w))

                inIf_logic.append(     inIf[-1].interfaceLogic(0)  )
                driver_logic.append(   inIf[-1].tb_driver()        )
                outIf_logic.append(    outIf[-1].interfaceLogic(0) )
                receiver_logic.append( outIf[-1].tb_receiver()     )

                tbInSig.append(        inIf[-1].driverSignals()  )
                tbOutSig.append(       outIf[-1].receiverInSignals()   ) 

            idata       = [Signal(intbv(0)[w:])                for w in width]
            ivalidBytes = [Signal(intbv(0, min=0, max=w//8+1))  for w in width]
            ifirst      = [Signal(intbv(0)[1:0])               for _ in width]
            ilast       = [Signal(intbv(0)[1:0])               for _ in width]
            ihalt       = [Signal(intbv(0)[1:0])               for _ in width]

            odata       = [Signal(intbv(0)[w:])                for w in width]
            ovalidBytes = [Signal(intbv(0, min=0, max=w//8+1))  for w in width]
            ofirst      = [Signal(intbv(0)[1:0])               for _ in width]
            olast       = [Signal(intbv(0)[1:0])               for _ in width]
            ohalt       = [Signal(intbv(0)[1:0])               for _ in width]

            iconn = []

            dut = self.createDUT(modName, blockName, postfix, cosim, synt,
                                 ['i',   'i',         'i',    'i',  'o',   'o',         'o',    'o',   'i', 'i',  'v'], store_and_forward,
                                   idata, ivalidBytes, ifirst, ilast, odata, ovalidBytes, ofirst, olast, clk, rstn, depth)

            dutInSig  = [[idata[i], None, ivalidBytes[i], ifirst[i], ilast[i]] for i in range(len(idata))]
            dutOutSig = [[odata[i], None, ovalidBytes[i], ofirst[i], olast[i]] for i in range(len(odata))]

            for i in range(len(idata)):
                for j in range(len(tbInSig[i])):
                    if tbInSig[i][j]!=None:
                        iconn.append(pass_through(tbInSig[i][j], dutInSig[i][j], name='tbIn_'+str(i)+'_'+str(j)))
                    if tbOutSig[i][j]!=None:
                        iconn.append(pass_through(dutOutSig[i][j], tbOutSig[i][j], name='tbOut_'+str(i)+'_'+str(j)))

            scoreboard = [ deque() for _ in range(len(width)) ]
            for i in range(nr):
                for port in range(len(inIf)):
                    p = inIf[port].random(minLen=min(64, (depth*width[port]//8)//4), maxLen=(depth*width[port]//8)//2)
                    inIf[port].push(p)
                    scoreboard[port].append(p)
#                print "Pushed packet", i
#                print p

            @instance
            def check():
                packets = [0 for _ in range(len(width)) ]
                totpack = 0
#                print "Run checker"
                yield rstn.posedge
#                print "Reset released"
                while True:
                    yield clk.posedge
                           
                    for port in range(len(outIf)):
                        if outIf[port].len() > 0:
                            p = outIf[port].pop()  
#                        print "popped packet", packets
#                        print p
#                        print scoreboard[0]
                            self.assertEqual(p, scoreboard[port][0])
                            from modules.common.Common import pktprint
                            #print "   Expected:"
                            #pktprint(scoreboard[port][1])
                            #print "   Got:"
                            #pktprint(p)
                            #print "   Diff:"
                            #pktprint(p, scoreboard[port][1])
                            scoreboard[port].popleft()
                            packets[port] += 1
                            totpack += 1
                            if totpack >= nr:
#                            print  "Tested RTL interface of width", w, "depth", depth, "with", packets, "packets"
                                yield clk.posedge
                                raise StopSimulation

            return instances()

        number_of_configurations = 5
        max_width_in_bytes = 7
        max_depth = 33
        min_depth = 11
        ports   = [2]
        widths  = [8*x for x in random.sample(range(1, max_width_in_bytes), number_of_configurations)]
        depths  = random.sample(range(min_depth, max_depth), number_of_configurations)
        speeds  = [1.0, 0.4]
        speeds.extend([random.randint(80, 99)/100.0 for _ in range(number_of_configurations-len(speeds))])
#        speeds  = [random.randint(90, 100)/100.0 for _ in range(number_of_configurations)]

        widths = [[24, 40]]
        depths = [15]
        speeds = [[0.5, 0.5]]
        packets = 10
        for w, d, s in zip(widths, depths, speeds):
            wstring = str(w).replace(" ", "").replace(",", "_").replace("[", "").replace("]", "")
            sstring = str(s).replace(" ", "").replace(",", "_").replace("[", "").replace("]", "")
            self.runSimulation(testbench, 'modules.common.store_and_forward', 'store_and_forward', '_w'+wstring+'_d'+str(d)+'_s'+sstring, w, d, s, packets)
               
if __name__ == '__main__':
    unittest.main()
