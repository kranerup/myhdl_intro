#!/usr/bin/python
# -*- coding: utf-8 -*-
from collections import deque
import unittest
from myhdl import *
from unittesting.ClockedTestCase import *
from .Common import *
from random import randrange, sample, randint

class UnitTest(unittest.TestCase, ClockedTestCase):

    def setUp(self):
        super(UnitTest, self).setUpSeed()
       
    def test_byteStream(self, tests=100, minLen=1, maxLen=1500):
       width = 16
       # Test byteStreams from seed
       seed = []
       streamA = []
       streamB = []
       outA    = []
       outB    = []
       doneA   = []
       doneB   = []

       doneCnt = 0
       for i in range(tests):
           length = minLen + randrange(maxLen-minLen)

           seed = randrange(2**32)

           streamA.append( byteStream(length=length, seed=seed, width=width) )
           streamB.append( byteStream(length=length, seed=seed, width=width) )
           outA.append([])
           outB.append([])
           doneA.append(False)
           doneB.append(False)
       while True:
           for i in range(len(doneA)):
               if not doneA[i]:
                   if randrange(3) == 0:
                       try:
                           t = next(streamA[i])
                           outA[i].append(t)
                       except:
                           doneA[i] = True
                           doneCnt += 1
           for i in range(len(doneB)):
               if not doneB[i]:
                   if randrange(3) == 0:
                       try:
                           t = next(streamB[i])
                           outB[i].append(t)
                       except:
                           doneB[i] = True
                           doneCnt += 1

           if doneCnt >= len(doneA) + len(doneB):
               break

       for i in range(tests):
           self.assertEqual(outA[i], outB[i])

    def test_byteStream_setByte(self, tests=20, minLen=2, maxLen=31):
       # Test byteStreams from seed
       # TODO: Test addBytes and delBytes
       width = 24
       seed = []
       outA    = []
       outB    = []
       doneA   = []
       doneB   = []

       doneCnt = 0
       for i in range(tests):
           outA    = []
           outB    = []
           length = minLen + randrange(maxLen-minLen)

           seed = randrange(2**32)

           streamA = byteStream(length=length, seed=seed, width=width)
           print("A", streamA)
           print("fletcher streamA") 
           hashA = getFletcherHash(length=length, seed=seed, width=width)
           print("hashA", hashA)
          
           for b in streamA:
               outA.append(b)
           print("aBytes", end=' ') 
           for i in outA:
               print(hex(i), end=' ')
           print()
           print("fletcher  outA")
           hashAbyte = getFletcherHash(data=outA, width=width)
           print("hashAbyte", hashAbyte)
           self.assertEqual(hashA, hashAbyte)

           owr_index = randrange(0, length)
           owr_data  = randrange(0, 256)
           print(" overwriting", owr_index)
           print(" orig       ", hex(outA[owr_index]), outA[owr_index])
           print(" new        ", hex(owr_data), owr_data)
           
           nr_of_bytes = width//8
           
           index = owr_index//nr_of_bytes
           byte =  owr_index - index*nr_of_bytes

           print("A", hex(outA[index]))
           owr_mask = 255 << byte*8
           data_mask = (2**width -1) ^ owr_mask
           masked = (outA[index] & data_mask)
           shifted = ( (owr_data  << byte*8) & owr_mask )
           temp = masked | shifted
           print("m", hex(masked))
           print("s", hex(shifted))
           print(bin(owr_mask), bin(data_mask), hex(temp))
           outA[index] = temp

           setBytes = {}
           setBytes[owr_index] = owr_data

           streamB = byteStream(length=length, seed=seed, width=width, setBytes=setBytes)
           hashB = getFletcherHash(length=length, seed=seed, width=width, setBytes=setBytes)
           print("hashB", hashB)
           print("B", streamB)
           for b in streamB:
               outB.append(b)
           print("bBytes", outB)
           hashBbyte = getFletcherHash(data=outB, width=width)
           self.assertEqual(hashB, hashBbyte)
           print("hashBbyte", hashBbyte)
           print("b", end=' ') 
           for i in outB:
               print(hex(i), end=' ')
           print()
           
           for j in range(len(outA)):
               self.assertEqual(outA[j], outB[j])

    def test_first_set_bit(self, tests=100, minLen=1, maxLen=7):
       # Test byteStreams from seed
       seed = []
       streamA = []
       streamB = []
       outA    = []
       outB    = []
       doneA   = []
       doneB   = []

       doneCnt = 0
       for i in range(tests):
           width = minLen + randrange(maxLen-minLen)
           nr = randrange(1<<width)
           a = Signal(intbv(nr)[width:])
           b = Signal(intbv(0, min=0, max=1<<width))
           res = fsb(nr)
           exp = 0
           for j in range(width):
               if a[j]==1:
                   exp = 1<<j
                   break
           #print "%s: exp %s, got %s" % (bin(nr), exp, res)        
           self.assertEqual(res, exp)

               
    def test_pass_through(self):
        """
        TODO: Test the compund list of signal types!
        """
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        def testbench(modName, blockName, postfix, w, convert_mode="", ival=None, nr=10, cosim=False, synt=False):
            
            clk = Signal(intbv(0)[1:0])
            rstn = Signal(intbv(0)[1:0])

            allow_mismatch = 0
            listLevel = 0
            wl = w
            while listType(wl):
                listLevel += 1
                wl= wl[0]
#            print "Testing pass_through with list level", listLevel, "and convert_mode", convert_mode
            print(conv)

            @instance
            def rstngen():
                rstn.next = 0
                yield delay(100)
                rstn.next = 1

            @always(delay(10))
            def clkgen():
                clk.next = not clk

            if listLevel==1:
                if convert_mode == "toList":
                    i = Signal(intbv(0)[compoundWidth(w):])
                    o = [Signal(intbv(0)[x:]) for x in w]
                elif convert_mode == "fromList":
                    i = [Signal(intbv(0)[x:]) for x in w]
                    o = Signal(intbv(0)[compoundWidth(w):])
                else:
                    i = [Signal(intbv(0)[x:]) for x in w]
                    o = [Signal(intbv(0)[x:]) for x in w]
            elif listLevel==2:
                if convert_mode == "toList":
                    i = Signal(intbv(0)[compoundWidth(w):])
                    o = [ [ Signal(intbv(0)[x:]) for x in w0] for w0 in w ]
                elif convert_mode == "fromList":
                    i = [ [ Signal(intbv(0)[x:]) for x in w0] for w0 in w ]
                    o = Signal(intbv(0)[compoundWidth(w):])
                else:
                    i = [ [ Signal(intbv(0)[x:]) for x in w0] for w0 in w ]
                    o = [ [ Signal(intbv(0)[x:]) for x in w0] for w0 in w ]
            elif listLevel==0:
                i = Signal(intbv(0)[w:])
                if convert_mode == "wide2narrow" and w > 1:
                    o = Signal(intbv(0)[w-1:])
                    allow_mismatch=1
                elif convert_mode == "narrow2wide":
                    o = Signal(intbv(0)[w+1:])
                    allow_mismatch=1
                else:
                    o = Signal(intbv(0)[w:])
                    
            else:
                print("ERROR! listLevel > 2 is not yet supported")
                assert False

            translate_off = 0
            if convert_mode == "int":
                from .Common import pass_int_dut
                dut = self.createDUT(
                    "modules.common.Common",
                    "pass_int_dut",
                    postfix,
                    cosim,
                    synt,
                    ['i', 'o', 'v', 'v', 'v'],
                    pass_int_dut,
                    i, o, ival, allow_mismatch, translate_off)
            elif convert_mode == "static":
                from .Common import pass_static_dut
                dut = self.createDUT(
                    "modules.common.Common",
                    "pass_static_dut",
                    postfix,
                    cosim,
                    synt, ['i', 'o', 'v', 'v', 'v'],
                    pass_static_dut,
                    i, o, ival, allow_mismatch, translate_off)
            else:
                dut = self.createDUT(modName, blockName, postfix, cosim, synt, ['i', 'o', 'v', 'v'], pass_through,
                                                                            i,   o, allow_mismatch, translate_off)
            if listLevel>0:
                @instance
                def driver():
                    while not rstn:
                        yield clk.posedge
                    for n in range(nr):
                        val = randSignal(i)
                        if signalType(i):
                            i.next = val
                        else:
                            for m in range(len(i)):
#                                print "   type:", type(i[m]).__name__
                                if not listType(i[m]):
                                    i[m].next = val[m]
                                else:
#                                    print "i", i
#                                    print "i[m]", i[m]
                                    for n in range(len(i[m])):
                                        if signalType(i[m][n]):
                                            i[m][n].next = val[m][n]
                                        else:
                                            print("ERROR! listLevel > 2 is not yet supported")
                                            assert False
                        yield clk.posedge
                        self.assertEqual(flatValue(o), flatValue(i))
                    yield clk.posedge
                    raise StopSimulation
            else:
                intmode = 0
                statmode = 0
                if convert_mode == "int":
                    intmode = 1
                if convert_mode == "static":
                    statmode = 1
                @instance
                def driver():
                    while not rstn:
                        yield clk.posedge
                    for n in range(nr):
                        if intmode or statmode:
                            val = ival
                            print("TB val =", val, ival)
                            sys.stdout.flush()
                            i.next = 0
                        else:
                            val = randrange(2**min([len(o), len(i)]))
                            i.next = val
                            
                        yield clk.posedge
                        self.assertEqual(int(o), val)
                    yield clk.posedge
                    raise StopSimulation
                    
            return instances()
        modes = ["static", "narrow2wide", "wide2narrow", "int", "signal", "list", "toList", "fromList", "listOfLists", "toListOfLists", "fromListOfLists"]
        runs_per_mode = 5
        ival = [ None for _ in range(runs_per_mode+1) ]
        for m in modes:
            print("TB: m =", m)
            sys.stdout.flush()
            if m == "int":
                widths = random.sample(range(1, 31), runs_per_mode)
                conv = m
            elif m == "static":
                widths = random.sample(range(1, 31), runs_per_mode)
                conv = m
            elif m == "wide2narrow":
                widths = random.sample(range(2, 32), runs_per_mode)
                conv = m
            elif m == "narrow2wide":
                widths = random.sample(range(1, 31), runs_per_mode)
                conv = m
            elif m == "signal":
                widths = random.sample(range(1, 31), runs_per_mode)
                conv = ""
            elif m == "list":
                widths = [random.sample(range(1, 31), random.randint(2, 5)) for _ in range(runs_per_mode)]
                conv = ""
            elif m == "listOfLists":
                widths = [[random.sample(range(1, 31), random.randint(2, 5)) for _ in range(4)] for __ in range(runs_per_mode)]
                conv = ""
            elif m == "toList" or m == "fromList":
                widths = [random.sample(range(1, 31), random.randint(2, 5)) for _ in range(runs_per_mode)]
                conv = m
            elif m == "toListOfLists" or m == "fromListOfLists":
                widths = [ [ random.sample(range(1, 31), random.randint(2, 5)) for _ in range(5)] for __ in range(runs_per_mode)]
                conv = m[0:-7]
            else:
                assert False
                
            if m == "fromList":
                widths.append([1, 1, 1, 1, 1, 1])
                
            if m == "int":
                ival = [ randrange(2**x) for x in widths ]
            elif m == "static":
                ival = [ randrange(2**x) for x in widths ]
            else:
                ival = [ None for _ in widths ]
            for i in range(len(widths)):
                w = widths[i]
                wstring = str(w).replace(" ", "").replace(",", "_").replace("[", "").replace("]", "")
                self.runSimulation(
                    testbench,
                    'modules.common.Common',
                    'pass_through',
                    '_w'+wstring+'_'+str(m),
                    w,
                    conv,
                    ival[i]
                )

    def test_pipeline(self):
        # The testbench needs to have the parameters cosim and synt, and they have to be set as false by default
        def testbench(modName, blockName, postfix, width, depth, start=0, nr=10, cosim=False, synt=False):

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

            idata = Signal(intbv(0)[width:])
            if width==1:
                stage = Signal(intbv(0)[depth:])
            else:
                stage = [Signal(intbv(0)[width:]) for _ in range(depth)]

            reset_value = 0
            clear = 0
            drive_first_stage = True
            
            dut = self.createDUT(
                modName, blockName, postfix, cosim, synt, 
                ['i', 'o', 'i',
                 'i', 'v', 'v', 'v',
                 'i'],
                pipeline,
                idata, stage, clk,
                rstn, start, reset_value,
                drive_first_stage, clear)
            
            clkCnt = Signal(intbv(0)[32:])

            scoreboard = []
            push_score = Signal(intbv(0)[1:0])
            @always(clk.posedge, rstn.negedge)
            def driver():
                if rstn==0:
                    clkCnt.next = 0
                    push_score.next = False
                else:
                    if push_score:
                        scoreboard.append(value(idata))
                    clkCnt.next = clkCnt + 1
                    val = randrange(2**len(idata))
                    idata.next = val
                    push_score.next = True
                    #print "pushed to scoreboard len="+str(len(scoreboard)), "cnt="+str(int(clkCnt))
                    for i in range(1, depth):
                        if 0 < clkCnt > i >= start:
                            #print "  i", i, len(stage), len(scoreboard), "clkCnt", clkCnt
                            #print scoreboard
                            self.assertEqual(value(stage[i]), scoreboard[clkCnt+start-i-1], "Mismatch in stage %d, expected %s but got %s. Start stage:%d" % (i, str(hex(scoreboard[clkCnt-i-1])), str(hex(value(stage[i]))), start))
                if clkCnt > depth*20:
                    raise StopSimulation
            @always(clk.negedge)
            def checkzero():
                if rstn==1 and push_score:
                    self.assertEqual(value(stage[start]), value(idata))
            return instances()
        
        runs = 10
        widths = random.sample(range(1, 129), runs)
        depths = random.sample(range(1, 21), runs)
        start =  [  randrange(d) for d in depths ]#
        widths.append(1)
        depths.append(7)
        start.append(0)
        widths.append(11)
        depths.append(1)
        start.append(0)
        widths.append(1)
        depths.append(7)
        start.append(0)
        widths.append(1)
        depths.append(7)
        start.append(3)
        for w, d, s in zip(widths, depths, start):
            self.runSimulation(
                testbench,
                'modules.common.Common',
                'pipeline',
                '_w'+str(w)+'_d'+str(d)+'_s'+str(s),
                w,
                d,
                s
            )
               
if __name__ == '__main__':
    unittest.main()
