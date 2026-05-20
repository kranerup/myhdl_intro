from myhdl import *
from random import randrange, sample, randint
import unittest
from unittesting.ClockedTestCase import *
from collections import deque
from .fifo_multi import fifo_multi
from .fifo_m_signal import fifo_m_signal
from .Common import value, pass_through, compoundSignal, compoundWidth, printHex
import sys

"""
Cosim failed: shadow signal
"""
class UnitTest(unittest.TestCase, ClockedTestCase):
    def setUp(self):
        super(UnitTest, self).setUpSeed()

    def test_fifo(self):
        modName = 'fifo_multi'
        blockName = 'fifo_multi'
        module = fifo_multi
        self.run_test_fifo(modName, blockName, module)

    def test_fifo_overclock(self):
        modName = 'fifo_m_signal'
        blockName = 'fifo_m_signal'
        module = fifo_m_signal
        self.run_test_fifo(modName, blockName, module)
        
    def run_test_fifo(self, modName, blockName, module):
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        # It needs to be named testbench
        modName = f"modules.common.{modName}"
        def testbench(modName, blockName, postfix, nr_of_fifos=3, w=16, d=5, iflop=0, oflop=0, push_latency=0, pop_latency=0, heads=1, mode='default', divisor=1, nr=1000, cosim=False, synt=False):

            print("test_fifo testbench with: nr_of_fifos=%d, w=%s, d=%d, iflop=%d, oflop=%d, push_latency=%d, pop_latency=%d, heads=%d, div=%s, nr=%d," % (nr_of_fifos, w, d, iflop, oflop, push_latency, pop_latency, heads, divisor,  nr))

            # Declare clock and reset
            clk   = Signal(intbv(0)[1:0]) 
            rstn  = Signal(intbv(0)[1:0]) 
            
            # Generate clock and reset
            @instance
            def rstngen():
                rstn.next = 0
                yield delay(100)
                rstn.next = 1

            if div==1:
                @always(delay(10))
                def clkgen():
                    clk.next = not clk
                clk_mult = None
            else:
                clk_master = Signal(intbv(0)[1:0]) 
                clk_mult   = Signal(intbv(0)[1:0]) 
                
                @always(delay(10))
                def clkgen():
                    clk_master.next = not clk_master
                from modules.common.Common import clock_divider
                iDivc = clock_divider(
                    master_clk = clk_master,
                    divisor = divisor*2,
                    clk = clk,
                    rstn = rstn,
                    name = "iDivc"
                )
                iDivm = clock_divider(
                    master_clk = clk_master,
                    divisor = 2,
                    clk = clk_mult,
                    rstn = rstn,
                    name = "iDivm"
                )
                
                
            pop2pop_min = [ Signal(intbv(0)[31:0]) for _ in range(nr_of_fifos)]
            push2push_min = [ Signal(intbv(0)[31:0]) for _ in range(nr_of_fifos)]
            pop2pop_cnt = [ Signal(intbv(0)[31:0]) for _ in range(nr_of_fifos)]
            push2push_cnt = [ Signal(intbv(0)[31:0]) for _ in range(nr_of_fifos)]
                
            listMode=False
            if listType(w):
                listMode=True
                tot_w = sum(w)
            else:
                tot_w = w
            
            print("w:", w)
            idata = compoundSignal(w)
            print("idata", type(idata).__name__, len(idata), idata)
            iflat = Signal(intbv(0)[compoundWidth(idata):])
            print("iflat", type(iflat).__name__, len(iflat), iflat)
            print(w, compoundWidth(idata))
            if heads==1:
                odata = [ compoundSignal(w) for _ in range(nr_of_fifos) ] 
            else:
                odata = compoundSignal(w)
            print("odata", type(odata).__name__, len(odata), odata)
            
            push_enable  = Signal(intbv(0)[1:0]) 
            push_sel     = Signal(intbv(0, min=0, max=nr_of_fifos)) 
            pop_enable   = Signal(intbv(0)[1:0]) 
            pop_enable_d1 = Signal(intbv(0)[1:0]) 
            pop_sel      = Signal(intbv(0, min=0, max=nr_of_fifos)) 
            pop_sel_d1   = Signal(intbv(0, min=0, max=nr_of_fifos)) 
            full  = Signal(intbv(0)[1:0]) 
            empty = Signal(intbv(0)[nr_of_fifos:0])
            level = [ Signal(intbv(0, min=0, max=d+1)) for _ in range(nr_of_fifos) ] 
            tot_level = Signal(intbv(0, min=0, max=d+1))
            
            zconn = []
            zconn.append(pass_through(iflat, idata, name="iflat"))

            scoreboard = [ deque() for _ in range(nr_of_fifos) ]
            result     = [ deque() for _ in range(nr_of_fifos) ]

            freeList = [ x for x in range(d) ]
            usedList = [ ]
            adrw  = (d-1).bit_length()
            restw = tot_w - adrw 
            
            pushRand    = Signal(intbv(0)[1:0])
            popRand     = Signal(intbv(0)[1:0])
            popSelRand  = Signal(intbv(0, min=0, max=nr_of_fifos)) 
            pushSelRand = Signal(intbv(0, min=0, max=nr_of_fifos)) 

            fullCnt = Signal(intbv(0))
            emptyCnt  = Signal(intbv(0))
            
            # Inverse probablilties for push and pop
            ipPush = Signal(intbv(0))
            ipPop  = Signal(intbv(0))

            popAll = Signal(intbv(0)[1:0]) # Set pop prob=1 when high 

#            highInverseProb = Signal(intbv(0)[31:0])
            highInverseProb = 3 # Probablility 1/3
            lowInverseProb = 2  # Probablility 1/2

            pipe = []
            push_oh = Signal(intbv(0)[nr_of_fifos:0])
            push_oh_d = [ copySignal(push_oh) for _ in range(push_latency+2 ) ]
            pipe.append(pipeline(push_oh, push_oh_d, clk, rstn, name="puh"))
            pop_oh = Signal(intbv(0)[nr_of_fifos:0])
            pop_oh_d = [ copySignal(pop_oh) for _ in range(pop_latency+2 ) ]
            pipe.append(pipeline(pop_oh, pop_oh_d, clk, rstn, name="poh"))
            @always_comb
            def poh_comb():
                push_oh.next = 0
                pop_oh.next = 0
                if push_enable==1:
                    push_oh.next[push_sel] = 1
                if pop_enable==1:
                    pop_oh.next[pop_sel] = 1
            pops   = [ Signal(intbv(0, min=0, max=pop_latency+2)) for _ in range(nr_of_fifos) ]
            if pop_latency>0:
                @always(clk.posedge, rstn.negedge)
                def pops_reg():
                    if rstn==0:
                        for i in range(nr_of_fifos):
                            pops[i].next = 0
                    else:
                        for i in range(nr_of_fifos):
                            pops[i].next = pops[i] + pop_oh_d[0][i] - pop_oh_d[pop_latency+1][i]
                
            # If we've become full more times than we've become empty set a higher pop probability (and vice versa)
            @always_comb
            def setProb():
                if fullCnt > emptyCnt:
                    ipPush.next = fullCnt - emptyCnt + highInverseProb
                    ipPop.next = lowInverseProb
                else:
                    ipPush.next = lowInverseProb
                    ipPop.next  = emptyCnt - fullCnt + highInverseProb
                if full:
                    ipPush.next = highInverseProb
                    ipPop.next = lowInverseProb
                all_empty = True
                for i in range(nr_of_fifos):
                    if not empty[i]:
                        all_empty = False
                if all_empty: 
                    ipPush.next = lowInverseProb
                    ipPop.next  = highInverseProb
                if popAll:
                    ipPush.next = 2**32
                    ipPop.next  = 1

            bar = progressbar(nr, " full posedges")
            sys.stdout.flush

            # Count the number of times we've become full
            @always(full.posedge)
            def countFull():
                if rstn == 0:
                    fullCnt.next = 0
                else:
                    bar.update(fullCnt)
                    fullCnt.next += 1

            last_empty = [ Signal(intbv(0)[1:0]) for _ in range(len(empty))]
            # Count the number of times we've become empty
            @always(clk.posedge, rstn.negedge)
            def countEmpty():
                if rstn == 0:
                    emptyCnt.next = 0
                    for i in range(len(empty)): 
                        last_empty[i].next = 1
                else:
                    for i in range(len(empty)): 
                        last_empty[i].next = empty[i]
                        if empty[i]==1 and last_empty[i]==0:
                            emptyCnt.next = emptyCnt + 1
                            
            # Toggle push and pop according to the probabilities
            @always(clk.posedge, rstn.negedge)
            def randomize():
                if rstn:
                    p = randrange(ipPush)==0
                    if mode=="link" and len(freeList)==0:
                        p = 0
                    iflat.next = dataGenerator(p)
                        
                    pushRand.next = p
                    push_sel.next = randrange(nr_of_fifos)
                    pop_sel.next = randrange(nr_of_fifos)
                    popRand.next = randrange(ipPop)==0
                    
            @always_comb
            def pushGen():
                push_enable.next = pushRand and not full

            @always_comb
            def popGen():
                if empty[pop_sel] or pops[pop_sel]>0:
                    pop_enable.next = 0
                else:
                    pop_enable.next = popRand

            # Generate the data
            def dataGenerator(valid=0):
                if mode=="link" and valid==1:
                    ix = randrange(len(freeList))
                    adr = freeList[ix]
                    #print "pushing index", ix, "adr", adr
                    sys.stdout.flush()
                    usedList.append(adr)
                    del freeList[ix]
                    return (randrange(2**restw)<<adrw) + adr 
                else:
                    return randrange(2**tot_w)

        
            # Push the generated data to the scoreboard
            @always(clk.posedge)
            def driver():
                if rstn:
                    if push_enable:
                        scoreboard[push_sel].append(value(idata))

######################################################################################3
#            This code checks the data as soon as it is valid, which is nice.
#            The drawback is that it hangs the testbench... for some reason.
#            Feel free to fix it!
#                         
#            # Check the outdata
#            @always(clk.posedge)
#            def checko():
#                if rstn:
#                    if pop_oh_d[pop_latency+1] > 0:
#                        for i in range(nr_of_fifos):
#                            if pop_oh_d[pop_latency+1][i]==1:
#                                if empty[i]==0:
#                                    if scoreboard[i][0] != value(odata[i]):
#                                        print "Mismatch for odata after pop_latency for queue %d. \n  %s expected but got\n  %s" %(i, printHex(scoreboard[i][0]), printHex(value(odata[i])))
#                                        self.assertEqual(1,0)
#                                else:
#                                    mismatch = 0
#                                    for v in odata[i]:
#                                        if v != 0:
#                                            mismatch = 1
#                                    if mismatch:
#                                        print "Mismatch! Expected 0 data when empty for queue %d, got %s" % (i,  value(odata[i]))
#                                        self.assertEqual(1,0)
#

            consistency_check = Signal(intbv(0)[1:])
            end_test = Signal(intbv(0)[1:])
            # Empty the queue and compare with the scoreboard
            @always(clk.posedge, rstn.negedge)
            def receiver():
                if rstn==0:
                    consistency_check.next = 0
                    end_test.next = 0
                    popAll.next = 0
                    pop_enable_d1.next = 0
                    pop_sel_d1.next = 0
                    for i in range(nr_of_fifos):
                        push2push_min[i].next = push2push_min[i].max-1
                        pop2pop_min[i].next = pop2pop_min[i].max-1
                        push2push_cnt[i].next = 0
                        pop2pop_cnt[i].next = 0
                else:                        
                    if end_test==1:
                        raise StopSimulation("Ah, done!")
                        
                    for i in range(nr_of_fifos):
                        push2push_cnt[i].next = push2push_cnt[i] + 1 
                        pop2pop_cnt[i].next =   pop2pop_cnt[i]   + 1
                    if push_enable:
                        if push2push_cnt[push_sel] < push2push_min[push_sel]:
                            push2push_min[push_sel].next = push2push_cnt[push_sel]
                            push2push_cnt[push_sel].next = 0
                    if pop_enable:
                        if pop2pop_cnt[pop_sel] < pop2pop_min[pop_sel]:
                            pop2pop_min[pop_sel].next = pop2pop_cnt[pop_sel]
                            pop2pop_cnt[pop_sel].next = 0
                            
                    pop_enable_d1.next = pop_enable
                    pop_sel_d1.next = pop_sel
                    if ((pop_enable and heads==1) or (pop_enable_d1 and heads==0)) and rstn:
                        if heads==1:
                            oval = value(odata[pop_sel])
                            osel = pop_sel
                        else:
                            oval = value(odata)
                            osel = pop_sel_d1
                        result[osel].append(oval)
                        if mode=="link":
                            adr = oval & ((1<<adrw)-1)
                            #print "popping ", adr
                            sys.stdout.flush()
                            freeList.append(adr)
                            usedList.remove(adr)
                        while len(result[osel])>0:
                            if result[osel][0] != scoreboard[osel][0]:
                                print("Mismatch!\n  %s expected for fifo %d, but got \n  %s" %(printHex(scoreboard[osel][0]), value(osel), printHex(result[osel][0])))
                                self.assertEqual(1, 0)
                            result[osel].popleft()
                            scoreboard[osel].popleft()
                    if fullCnt >= nr and emptyCnt >= nr:
                        bar.finish()
                        #print "Stopping after", fullCnt, "full and", emptyCnt, "empties.", len(result), "operations"
                        popAll.next = 1
                        if popAll==0:
                            pass
                            #print 
                            #print "Popping all"
                            #print 
                        allZero = 1
                        for i in range(len(level)):
                            if level[i] > 0:
                                allZero = 0
                        if allZero:
                            #print "allZero"
                            sys.stdout.flush()
                            for i in range(len(result)):
                                print("FIFO", i)
                                for j in range(len(result[i])):
                                    print('  r', hex(result[i][0]), 's', hex(scoreboard[i][0]))
                                    if result[i][0] != scoreboard[i][0]:
                                        print("Mismatch!\n%s from dut != \n%s from scoreboard" %(printHex(result[i][0]), printHex(scoreboard[i][0])))
                                        self.assertEqual(1, 0)
                            #print "Bye-bye!"
                            sys.stdout.flush()
                            print("Min push2push", end=' ')
                            for n in push2push_min:
                                print(int(n), end=' ')
                            print()
                            print("Min pop2pop", end=' ')
                            for n in pop2pop_min:
                                print(int(n), end=' ')
                            print()
                            consistency_check.next = 1
                            end_test.next = 1
                            
            two_and_up = None
            if blockName!="fifo_m_signal":
                # Here we create the DUT and generate the RTL (if necessary)
                dut = self.createDUT(modName, blockName, postfix, cosim, synt,
                                     ['i',  'o', 'i',        'i',     'i',       'i',    'o', 'o',  'o',  'o',      'i', 'i',       'i',         'v', 'v', 'v',   'v',          'v',       'v',  'v',    'o'], module,
                                     idata, odata, push_enable, push_sel, pop_enable, pop_sel, full, empty, level, tot_level, clk, rstn, consistency_check, d, iflop, oflop, push_latency, pop_latency, mode, heads, two_and_up)
            else:
                # Here we create the DUT and generate the RTL (if necessary)
                dut = self.createDUT(modName, blockName, postfix, cosim, synt,
                                     ['i',  'o', 'i',        'i',     'i',       'i',    'o', 'o',  'o',  'o',       'i', 'i',       'i',           'i',     'v',  'v', 'v',   'o', 'v', 'v',  ], module,
                                     idata, odata, push_enable, push_sel, pop_enable, pop_sel, full, empty, level, tot_level, clk, rstn, consistency_check, clk_mult, divisor, d, heads, two_and_up, iflop, oflop, )
                
            return instances()
        ### End of tb ###
        
        ### run_test_fifo_or_lifo continues ###

        # Randomize the hardware configuration
        
        loops = 5
        inflop  = [0] # TODO: inflop = 1 is not done, and should not be part of the regression.
#        outflop = [0,1]
        outflop = [0]
        heads = [0, 1]
        latency = [0, 2]
        mode = ["link", "default"]

        if modName == "fifo_m_signal":
            mode = ["default"]
            latency = [0]
            
        # Use this to reproduce one instance:
        #self.runSimulation(testbench, modName, blockName,
        #    '_w85_f6_d33_if0_of0_lat0_heads0',
        #    6, #nr_of_fifos=6,
        #    85, #w=85,
        #    33, #d=33,
        #    0, #iflop=0,
        #    0, #oflop=0,
        #    0, #push_latency=0,
        #    0, #pop_latency=0,
        #    0, #heads=0,
        #    1000)#nr=1000)

        for _ in range(loops):
            for iflop in inflop:
                for oflop in outflop:
                    for m in mode:
                        for lat in latency:
                            for h in heads:
                                if m=="default":
                                    if not (h==1 or (lat==0 and oflop==0 and iflop==0)):
                                        print("A skipping", m, h, lat, oflop, iflop)
                                        continue
                                if m=="link":
                                    if lat>0:
                                        print("B skipping", m, h, lat, oflop, iflop)
                                        continue
                                    if h!=1:
                                        print("C skipping", m, h, lat, oflop, iflop)
                                        continue
                                f = randrange(2, 33)
                                mind = (f+lat*2)
                                d = randrange(mind*2+1, mind*4+1)
                                if m=="link":
                                    rest = randrange(1, 10)
                                    w = (d).bit_length()+rest
                                else:
                                    w = randrange(1, 100)
                                if modName=="fifo_m_signal":
                                    w = randrange(16, 1024)
                                    div = randrange(w-2)+2
                                else:
                                    div=1
                                wstring = str(w).replace(" ", "").replace(",", "_").replace("[", "").replace("]", "")
                                print("w", w, "d", d, "f", f, "if", iflop, "of", oflop, "lat", lat, "heads", h, "mode", m, "div", div)
                                sys.stdout.flush()
                                # Simulate the hardware configuration
                                self.runSimulation(testbench, modName, blockName, '_w'+wstring+"_f"+str(f)+"_d"+str(d)+"_if"+str(iflop)+"_of"+str(oflop)+"_lat"+str(lat)+"_heads"+str(h)+"_mode"+str(m)+"_div"+str(div), f, w, d, iflop, oflop, lat, lat, h, m, div)
                    
# This is needed for automatically running the unit tests
if __name__ == '__main__':
    unittest.main()
