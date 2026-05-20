from myhdl import *
from modules.common.Common import copySignal, pass_through, listOfSignalsType

def compare(ival1, ival2, oval1, oval2, up):

    @always_comb
    def logic():
        oval1.next = ival1
        oval2.next = ival2
        if up == (ival1 > ival2):
            oval1.next = ival2
            oval2.next = ival1

    return logic

def feedthru(a, z):

    @always_comb
    def logic():
        z.next = a

    return logic

def bitonicMerge(ival, oval, up):

    n = len(ival)
    k = n//2
    w = len(ival[0])

    if n > 1:
        vt = [Signal(intbv(0)[w:]) for i in range(n)]
        comp = [ compare(ival[i], ival[i+k], vt[i], vt[i+k], up) for i in range(k)]
        loMerge = bitonicMerge(vt[:k], oval[:k], up)
        hiMerge = bitonicMerge(vt[k:], oval[k:], up)
        return comp, loMerge, hiMerge
    else:
        feedv = feedthru(ival[0], oval[0])
        return feedv

def bitonicSort(ival, oval, up):

    n = len(ival)
    k = n//2
    w = len(ival[0])

    if n > 1:
        vt = [Signal(intbv(0)[w:]) for i in range(n)]
        loSort = bitonicSort(ival[:k], vt[:k], 1)
        hiSort = bitonicSort(ival[k:], vt[k:], 0)
        merge = bitonicMerge(vt, oval, up)
        return loSort, hiSort, merge
    else:
        feedv = feedthru(ival[0], oval[0])
        return feedv

    
@module
def bitonic_sorter(data, ordered):
    
    dw = len(data[0])
    aw = len(data)
    aw_w = (aw-1).bit_length()
            
    iSorter = bitonicSort(data, ordered, 0)

    return instances()


