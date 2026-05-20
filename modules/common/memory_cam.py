from myhdl import *
from .Common import (
    pass_through,
    pass_through_old,
    sliceSignal,
    signalType,
    listType,
    copySignal,
    mux2,
    flop,
    compoundWidth,
    multiflop,
)
from modules.common.Common import hwdir, rootdir
import sys
import os
sys.path.append(hwdir())
sys.path.append(os.path.join(hwdir(), "hdl"))
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()
import shutil


def memory_cam(idata,odata,raddr,waddr,renable,wenable,
               clk,rstn,depth,
               cam_search,cam_key,cam_answer,cam_mask=False,key_mask=False,
               input_flops = 0, output_flops = 0,
               name=""):

    """
    This module contains a CAM model in myHDL, and possible to use a third party CAM model for RTL.

    Data structures:
    idata & odata:
       If RD/WR interface has a mask, the data structure is: {valid,mask,data},
       else: {valid,data}

    cam_key:
       if cam search includes a key mask: the structure for cam_key is {mask,key}

    cam_answer: {index,hit}
    """


#---------------------------------------------
# IO flops
    idatam    = copySignal(idata)
    raddrm    = copySignal(raddr)
    waddrm    = copySignal(waddr)
    renablem  = copySignal(renable)
    wenablem  = copySignal(wenable)
    cam_searchm = copySignal(cam_search)
    cam_keym    = copySignal(cam_key)
    odatam    = copySignal(odata)
    cam_answerm = copySignal(cam_answer)

    zMf = []
    zMf.append( multiflop( idata,       idatam, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( raddr,       raddrm, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( waddr,       waddrm, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( renable,     renablem, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( wenable,     wenablem, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( cam_search,  cam_searchm, clk, rstn, depth=input_flops ) )
    zMf.append( multiflop( cam_key,     cam_keym, clk, rstn, depth=input_flops ) ) 
    if hwconf.cam_model == 'cavium':
        zMf.append( multiflop( odatam,      odata, clk, rstn, depth=output_flops-1 ) )
        zMf.append( multiflop( cam_answerm, cam_answer, clk, rstn, depth=output_flops-1 ) )
    else:    
        @always_comb
        def outpass():
            odata.next = odatam
            cam_answer.next = cam_answerm
#--------------------------------------------                
    

    if key_mask:
        data_width = len(cam_key)//2
    else:
        data_width = len(cam_key)
    width = data_width+1

    if cam_mask:
        if len(idata) != (data_width*2)+1:
            print("ERROR! CAM width mismatch in", name, "RD/WR interface:", len(idata), "search interface:", (data_width*2)+1)
            assert False
    else:
        if len(idata)  != width:
            print("ERROR! CAM width mismatch in", name, "RD/WR interface:", len(idata), "search interface:", width)
            assert False

    zPs = []

    senable   = Signal(intbv(0)[1:0])
    skey      = Signal(intbv(0)[width-1:0])
    smask     = Signal(intbv(0)[width-1:0])
    sindex    = Signal(intbv(0, min=0, max=depth))
    shit      = Signal(intbv(0)[1:0])
    rwaddr    = Signal(intbv(0, min=0, max=depth))
    wdata     = Signal(intbv(0)[width-1:0])
    wmask     = Signal(intbv(0)[width-1:0])
    wvalid    = Signal(intbv(0)[1:0])
    rdata     = Signal(intbv(0)[width-1:0])
    rmask     = Signal(intbv(0)[width-1:0])
    rvalid    = Signal(intbv(0)[1:0])


    if cam_mask:
        zPs.append(pass_through(idatam, [wdata, wmask, wvalid], name=name+".ida"))
        zPs.append(pass_through([rdata, rmask, rvalid], odatam, name=name+".rda"))
    else:
        zPs.append(pass_through(idatam, [wdata, wvalid], name=name+".ida2"))
        zPs.append(pass_through([rdata, rvalid], odatam, name=name+".rda2"))
        @always(clk.posedge, rstn.negedge)
        def setwmask():
            if rstn == 0:
                wmask.next = 0
            else:
                wmask.next = 0

    if key_mask:
        zPs.append(pass_through(cam_keym, [skey, smask], name=name+".skey"))
    else:
        zPs.append(pass_through(cam_keym, skey, name=name+".skey2"))
        @always(clk.posedge, rstn.negedge)
        def setsmask():
            if rstn == 0:
                smask.next = 0
            else:
                smask.next = 0

    @always_comb
    def camin():
        senable.next = cam_searchm
        rwaddr.next = raddrm | waddrm


    @always_comb
    def camout():
        cam_answerm.next = concat(sindex, shit)
        
    
    if hwconf.cam_model == 'default' or hwconf.cam_model == 'default_rmask':

        use_rmask = hwconf.cam_model == 'default_rmask'
        
        iCamDefault = myhdl_model(
            senable      = senable,
            skey         = skey,
            smask        = smask,
            sindex       = sindex,
            shit         = shit,
            renable      = renablem,
            wenable      = wenablem,
            wdata        = wdata,
            wmask        = wmask,
            wvalid       = wvalid,
            rdata        = rdata,
            rmask        = rmask,
            rvalid       = rvalid,
            rwaddr       = rwaddr,
            clk          = clk,
            rstn         = rstn,
            depth        = depth,
            input_flops  = input_flops,
            output_flops = output_flops,
            use_rmask    = use_rmask,
            name         = name+".cav.cam")
        
            
    elif hwconf.cam_model == 'cavium':

        assert output_flops==1, """
The TCAM has an internal pipeline so it can not support output_flops=0. 
Higher delays could however be implemented."""
        
        
        reset     = Signal(intbv(0)[1:0])
        reset_d0  = Signal(intbv(0)[1:0])

        @always(clk.posedge, rstn.negedge)
        def getReset():
            if rstn==0:
                reset_d0.next = 1
                reset.next = 0
            else:
                reset_d0.next = 0
                reset.next = reset_d0

        iCav = cavium_model(
            senable     = senable,
            skey        = skey,
            smask       = smask,
            sindex      = sindex,
            shit        = shit,
            renable     = renablem,
            wenable     = wenablem,
            wdata       = wdata,
            wmask       = wmask,
            wvalid      = wvalid,
            rwaddr      = rwaddr,
            rdata       = rdata,
            rmask       = rmask,
            rvalid      = rvalid,
            clk         = clk,
            rstn        = rstn,
            reset       = reset,
            depth       = depth,
            name        = name+".cav.cam")

    return instances()



def myhdl_model(senable,skey,smask,sindex,shit,
                renable,wenable,wdata,wmask,wvalid,rwaddr,rdata,rmask,rvalid,
                clk,rstn,depth,input_flops,output_flops,use_rmask,name=''):
    
    """

    """

    data_width = len(skey)
    width = data_width + 1

    max_width = 64 # TODO(yian180516) Configurable
    nr_of_groups = (data_width+max_width-1)//max_width

    idata = [wdata, wmask, wvalid] # Reversed order to use pass_through !!
    odata = [rdata, rmask, rvalid]

    
    idata_flat = Signal(intbv(0)[compoundWidth(idata):])
    odata_flat = Signal(intbv(0)[compoundWidth(idata):])
    odata_mask = copySignal(odata_flat)
    data = [ copySignal(idata_flat) for _ in range(depth) ]

    zPs = []
    zPs.append(pass_through(idata, idata_flat, name=name+".passi"))
    zPs.append(multiflop(odata_mask, odata, clk, rstn, depth=output_flops, name=name+".passo"))

    

    ################################
    # Read and write
    @always(clk.posedge, rstn.negedge)
    def outlogic():
        if rstn==0:
            odata_flat.next = 0
        else:
            odata_flat.next = 0
            if renable==1:
                odata_flat.next = data[rwaddr]
                if wenable==1:
                    odata_flat.next = idata_flat


    if use_rmask:
        # Mask the read out data, not necessary but the other tcam model uses this.
        @always_comb
        def outmask():
            tmp_data = modbv(0)[data_width:0]
            tmp_mask = modbv(0)[data_width:0]
            tmp_valid = modbv(0)[1:0]
            tmp_data[:] = odata_flat
            tmp_mask[:] = odata_flat >> data_width
            tmp_valid[:] = odata_flat >> (data_width*2)

            tmp_data[:] = tmp_data & (~tmp_mask)
            odata_mask.next = concat(tmp_valid, tmp_mask, tmp_data)
    else:
        @always_comb
        def outmask():
            odata_mask.next = odata_flat



    @always(clk.posedge, rstn.negedge)
    def memlogic():
        if rstn==0:
            for i in range(depth):
                data[i].next = 0
        else:
            if wenable==1:
                data[rwaddr].next = idata_flat
    ################################
    # Search
    iSub = []
    sindex_d0 = copySignal(sindex)
    shit_d0 = copySignal(shit)

    sub_skey  = [Signal(modbv(0)[max_width:0])  for _ in range(nr_of_groups)]
    sub_smask = [Signal(modbv(0)[max_width:0])  for _ in range(nr_of_groups)]
    sub_hit_list = [Signal(modbv(0)[depth:0])   for _ in range(nr_of_groups)]

    @always_comb
    def subSearchIn():
        for i in range(nr_of_groups):
            sub_skey[i].next = skey >> (max_width*i)
            sub_smask[i].next = smask >> (max_width*i)
    
    # Parallel sub search, each costs one cycle
    for i in range(nr_of_groups):
        compare_bits = min(data_width-max_width*i, max_width)
        
        iSub.append(sub_search(
            data          = data,
            senable       = senable,
            skey          = sub_skey[i],
            smask         = sub_smask[i],
            hit_list      = sub_hit_list[i],
            clk           = clk,
            rstn          = rstn,
            shift_bits    = max_width*i,
            compare_bits  = compare_bits,
            data_width    = data_width,
            name          = name+'.sub'))


    # Merge the search result
    @always_comb
    def searchMerge():
        merged_list = modbv(0)[depth:0]
        merged_list[:] = 2**depth-1
        for i in range(nr_of_groups):
            merged_list[:] = merged_list & sub_hit_list[i]
        # Find the first hit
        idx = intbv(0, min=0, max=depth)
        hit = intbv(0)[1:0]
        for i in range(depth):
            if merged_list[i]==1 and hit==0:
                idx[:] = i
                hit[:] = 1
        sindex_d0.next = idx
        shit_d0.next = hit

        

    zOfsi = multiflop(sindex_d0, sindex, clk, rstn, depth=output_flops)
    zOfsh = multiflop(shit_d0, shit, clk, rstn, depth=output_flops)

    return instances()
                

def sub_search(data,senable,skey,smask,hit_list,clk,rstn,shift_bits=0,compare_bits=0,data_width=0,name=""):

    hit_list_d0 = copySignal(hit_list)
    depth = len(hit_list)
    
    @always_comb
    def searchKey():
        sub_data = modbv(0)[compare_bits:0]
        sub_mask = modbv(0)[compare_bits:0]
        tmp_m = modbv(0)[data_width:0] # mask
        tmp_d = modbv(0)[data_width:0] # data
        tmp_hit = modbv(0)[depth:0]
        tmp_valid = modbv(0)[1:0]
        masked_key  = modbv(0)[compare_bits:0]
        masked_data = modbv(0)[compare_bits:0]

        for i in range(depth):
            tmp_d[:] = data[i]
            tmp_m[:] = data[i]>>data_width
            tmp_valid[:] = data[i]>>(data_width*2)
            
            sub_data[:] = tmp_d>>shift_bits
            sub_mask[:] = tmp_m>>shift_bits
            sub_mask[:] = ~sub_mask
            
            masked_key[:] = skey & (~smask)
            masked_key[:] = masked_key & sub_mask
            masked_data[:] = sub_data & (~smask)
            masked_data[:] = masked_data & sub_mask
            
            if masked_key == masked_data and tmp_valid==1:
                tmp_hit[i] = 1

        if senable==1:
            hit_list_d0.next = tmp_hit
        else:
            hit_list_d0.next = 0


    @always(clk.posedge, rstn.negedge)
    def hitFF():
        if rstn == 0:
            hit_list.next = 0
        else:
            hit_list.next = hit_list_d0

    return instances()


def cavium_model(senable,skey,smask,sindex,shit,renable,wenable,wdata,wmask,wvalid,rwaddr,rdata,rmask,rvalid,clk,rstn,reset,depth,name=''):
    """
    cam_ternary
    """

    data_width = len(skey)
    width = data_width+1
    module_name = "p1_tcam_wrap"
    wname = "cam_ternary"

    s = os.path.join(rootdir(), "modules/common/"+wname+".v")
    d = os.path.join(hwdir(), "hdl/"+wname+".sv")
    if not os.path.isfile(d):
        print(name, "Copying", s, "to", d)
        shutil.copy(s, d)

    idata = [wdata, wmask, wvalid] # Reversed order to use pass_through !!
    odata = [rdata, rmask, rvalid]

    
    idata_flat = Signal(intbv(0)[compoundWidth(idata):])
    odata_flat = Signal(intbv(0)[compoundWidth(idata):])
    odata_mask = copySignal(odata_flat)
    data = [ copySignal(idata_flat) for _ in range(depth) ]

        
    zPs = []
    # Need to use old pass through as new does not play well with __verilog__
    zPs.append(pass_through_old(idata, idata_flat, name=name+".passi"))
    zPs.append(pass_through_old(odata_mask, odata, name=name+".passo"))

        
    sindex_d0 = copySignal(sindex)
    shit_d0 = copySignal(shit)
    sindex_d1 = copySignal(sindex)
    shit_d1  = copySignal(shit)

    @always_comb
    def searchKey():
        idx = intbv(0, min=0, max=depth)
        hit = intbv(0)[1:0]
        tmp_m = modbv(0)[data_width:0] # mask
        tmp_d = modbv(0)[data_width:0] # data
        masked_key  = modbv(0)[data_width:0]
        masked_data = modbv(0)[data_width:0]
        tmp_valid = modbv(0)[1:0]
        if senable==1:
            for i in range(depth):
                tmp_d[:] = data[i]
                tmp_m[:] = data[i]>>data_width
                tmp_m[:] = ~tmp_m
                tmp_valid[:] = data[i]>>(data_width*2)
                masked_key[:] = skey & (~smask)
                masked_key[:] = masked_key & tmp_m
                masked_data[:] = tmp_d & (~smask)
                masked_data[:] = masked_data & tmp_m
                if masked_key == masked_data and tmp_valid==1:
                    idx[:] = i
                    hit[:] = 1
        sindex_d0.next = idx
        shit_d0.next = hit
    @always(clk.posedge, rstn.negedge)
    def searchFF():
        if rstn==0:
            sindex.next = 0
            shit.next = 0
            sindex_d1.next = 0
            shit_d1.next = 0
        else:
            sindex.next = sindex_d1
            shit.next = shit_d1
            sindex_d1.next = sindex_d0
            shit_d1.next = shit_d0

            
    @always(clk.posedge, rstn.negedge)
    def outlogic():
        if rstn==0:
            odata_flat.next = 0
        else:
            odata_flat.next = 0
            if renable==1:
                odata_flat.next = data[rwaddr]
                if wenable==1:
                    odata_flat.next = idata_flat

    # Mask the read out data, not necessary but the other tcam model uses this.
    @always(clk.posedge, rstn.negedge)
    def outmask():
        if rstn == 0:
            odata_mask.next = 0
        else:
            tmp_data = modbv(0)[data_width:0]
            tmp_mask = modbv(0)[data_width:0]
            tmp_valid = modbv(0)[1:0]
            tmp_data[:] = odata_flat
            tmp_mask[:] = odata_flat >> data_width
            tmp_valid[:] = odata_flat >> (data_width*2)

            tmp_data[:] = tmp_data & (~tmp_mask)
            odata_mask.next = concat(tmp_valid, tmp_mask, tmp_data)
        

    @always(clk.posedge, rstn.negedge)
    def memlogic():
        if rstn==0:
            for i in range(depth):
                data[i].next = 0
        else:
            if wenable==1:
                data[rwaddr].next = idata_flat

                
                
    shit.driven = "wire"
    sindex.driven = "wire"
    rdata.driven = "wire"
    rmask.driven = "wire"
    rvalid.driven = "wire"
    __verilog__ = \
"""
// 
{module_name} 
 #(
   .NENT({depth}),
   .WIDTH({width}),
   .MATCH_HIGHEST(0)
 )
 {name}Tcam(
   // Misc clocking and control signals
   .clk(          %(clk)s),
   // CAM lookup
   .ccmd_0a(       %(senable)s),
   .icmd_0a(       %(reset)s),
   .cdat_0a(       %(skey)s),
   .cmsk_0a(       %(smask)s),
   .hitvec_1a(),
   .hitidx_1a(),
   .hit_1a(),
   .multihit_1a(),
   .hitidx_2a(     %(sindex)s),
   .hit_2a(        %(shit)s),
   // RD/WR interface
   .rcmd_0a(       %(renable)s),
   .wcmd_0a(       %(wenable)s),
   .wdat_0a(       %(wdata)s),
   .wmsk_0a(       %(wmask)s),
   .wdat_val_0a(   %(wvalid)s),
   .rwidx_0a(      %(rwaddr)s),
   .rdat_2a(       %(rdata)s),
   .rdat0_2a(),
   .rmsk_2a(       %(rmask)s),
   .rdat_val_2a(   %(rvalid)s)
 );
""".format(
    width         = width, 
    depth         = depth, 
    name          = name.replace(".", "_"),
    module_name   = module_name)

    return instances()

