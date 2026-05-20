import sys
from myhdl import *
from modules.common.Common import copySignal, pass_through, multiflop
from modules.common.Common import hwdir
sys.path.append(hwdir())
from modules.common.hwconf import get_hwconf; hwconf = get_hwconf()


def mmd_algo(
        read_info,
        pkt_bytes,
        icolor,
        idrop,
        ocolor,
        odrop,
        conf_read_valid,
        conf_read_addr,
        conf_otoken_1,
        conf_otoken_2,
        conf_osply_token_1,
        conf_osply_token_2,
        conf_ocap_1,
        conf_ocap_2,
        conf_oentry_reset,
        conf_mmd_mode,
        conf_drop_mode,
        conf_adj_token,
        conf_adj_mode,
        
        conf_write_valid,
        conf_write_addr,
        conf_itoken_1,
        conf_itoken_2,
        clk,
        rstn,
        bucket_w,
        algo_latency,
        MMD_LATENCY,
        name):



    leaked_tokens = copySignal(pkt_bytes)
    init_color = copySignal(icolor)
    init_drop  = copySignal(idrop)
    sply_token_1 = Signal(modbv(0)[bucket_w:0])
    sply_token_2 = Signal(modbv(0)[bucket_w:0])
    read_done   = Signal(intbv(0)[1:0])
    read_done_addr = copySignal(conf_read_addr)

    # Decode read_info
    zPsInfo = pass_through(read_info, [conf_read_valid, conf_read_addr], name=name+".crv")

    zPip = []

    zPip.append(multiflop(conf_read_valid, read_done, clk, rstn, depth=MMD_LATENCY, name=name+".readvalid"))
    zPip.append(multiflop(conf_read_addr, read_done_addr, clk, rstn, depth=MMD_LATENCY, name=name+".readaddr"))
    zPip.append(multiflop(pkt_bytes, leaked_tokens, clk, rstn, depth=MMD_LATENCY, name=name+".tokens"))
    zPip.append(multiflop(icolor, init_color, clk, rstn, depth=MMD_LATENCY, name=name+".color"))
    zPip.append(multiflop(idrop, init_drop, clk, rstn, depth=MMD_LATENCY, name=name+".drop"))
    
    zPip.append(multiflop(read_done, conf_write_valid, clk, rstn, depth=algo_latency))
    zPip.append(multiflop(read_done_addr, conf_write_addr, clk, rstn, depth=algo_latency))


    iAlgo = token_algorithm(
        read_done        =  read_done,
        entry_reset      =  conf_oentry_reset,
        cap_1            =  conf_ocap_1,
        cap_2            =  conf_ocap_2,
        itoken_1         =  conf_otoken_1,
        itoken_2         =  conf_otoken_2,
        sply_token_1     =  conf_osply_token_1,
        sply_token_2     =  conf_osply_token_2, 
        adj_token        =  conf_adj_token,
        adj_mode         =  conf_adj_mode,
        mmd_mode         =  conf_mmd_mode,
        drop_mode        =  conf_drop_mode,
        leaked_tokens    =  leaked_tokens,
        icolor           =  init_color,
        idrop            =  init_drop,
        otoken_1         =  conf_itoken_1,
        otoken_2         =  conf_itoken_2,
        odrop            =  odrop,
        ocolor           =  ocolor,
        clk              =  clk,
        rstn             =  rstn,
        bucket_w         =  bucket_w,
        algo_latency     =  algo_latency,
        name             =  name+'.algo')

        
    return instances()

"""
Read conf, check unchange, tick counting

color_map: 3bits saying drop or not
"""
def token_algorithm(
        read_done,
        entry_reset,
        cap_1,
        cap_2,
        itoken_1,
        itoken_2,
        sply_token_1,
        sply_token_2,
        adj_token,
        adj_mode,
        mmd_mode,
        drop_mode,
        leaked_tokens,
        idrop,
        icolor,
        otoken_1,
        otoken_2,
        odrop,
        ocolor,
        clk,
        rstn,
        bucket_w,
        algo_latency,
        name = ""):

    # Should match the conf settings
    GREEN  = 0
    YELLOW = 1
    RED    = 2
    

        
    """
    RFC 2697            A Single Rate Three Color Marker 

   The behavior of the Meter is specified in terms of its mode and two
   token buckets, C and E, which both share the common rate CIR.  The
   maximum size of the token bucket C is CBS and the maximum size of the
   token bucket E is EBS.

   The token buckets C and E are initially (at time 0) full, i.e., the
   token count Tc(0) = CBS and the token count Te(0) = EBS.  Thereafter,
   the token counts Tc and Te are updated CIR times per second as
   follows:

     o If Tc is less than CBS, Tc is incremented by one, else

     o if Te is less then EBS, Te is incremented by one, else

     o neither Tc nor Te is incremented.

   When a packet of size B bytes arrives at time t, the following
   happens if the srTCM is configured to operate in the Color-Blind
   mode:

     o If Tc(t)-B >= 0, the packet is green and Tc is decremented by B
       down to the minimum value of 0, else

     o if Te(t)-B >= 0, the packets is yellow and Te is decremented by B
       down to the minimum value of 0, else

     o the packet is red and neither Tc nor Te is decremented.

   When a packet of size B bytes arrives at time t, the following
   happens if the srTCM is configured to operate in the Color-Aware
   mode:

     o If the packet has been precolored as green and Tc(t)-B >= 0, the
       packet is green and Tc is decremented by B down to the minimum
       value of 0, else

     o If the packet has been precolored as green or yellow and if
       Te(t)-B >= 0, the packets is yellow and Te is decremented by B
       down to the minimum value of 0, else

     o the packet is red and neither Tc nor Te is decremented.

   Note that according to the above rules, marking of a packet with a
   given color requires that there be enough tokens of that color to
   accommodate the entire packet.  Other marking policies are clearly
   possible. The above policy was chosen in order guarantee a

    ###################################################################
    RFC 2698             A Two Rate Three Color Marker

   The behavior of the Meter is specified in terms of its mode and two
   token buckets, P and C, with rates PIR and CIR, respectively.  The
   maximum size of the token bucket P is PBS and the maximum size of the
   token bucket C is CBS.

   The token buckets P and C are initially (at time 0) full, i.e., the
   token count Tp(0) = PBS and the token count Tc(0) = CBS.  Thereafter,
   the token count Tp is incremented by one PIR times per second up to
   PBS and the token count Tc is incremented by one CIR times per second
   up to CBS.

   When a packet of size B bytes arrives at time t, the following
   happens if the trTCM is configured to operate in the Color-Blind
   mode:

     o If Tp(t)-B < 0, the packet is red, else

     o if Tc(t)-B < 0, the packet is yellow and Tp is decremented by B,
       else

     o the packet is green and both Tp and Tc are decremented by B.

   When a packet of size B bytes arrives at time t, the following
   happens if the trTCM is configured to operate in the Color-Aware
   mode:

     o If the packet has been precolored as red or if Tp(t)-B < 0, the
       packet is red, else

     o if the packet has been precolored as yellow or if Tc(t)-B < 0,
       the packet is yellow and Tp is decremented by B, else

     o the packet is green and both Tp and Tc are decremented by B.

   The actual implementation of a Meter doesn't need to be modeled
   according to the above formal specification.

   """


    ocolor_d0   = copySignal(ocolor)
    odrop_d0    = copySignal(odrop)
    new_color   = copySignal(ocolor)
    

    adj_bytes = copySignal(leaked_tokens)
    new_token_1 = copySignal(otoken_1)
    new_token_2 = copySignal(otoken_2)

    
    # Packet size correction
    @always_comb
    def pktBytes():
        if adj_mode==0:
            adj_bytes.next = leaked_tokens+adj_token
        else:
            adj_bytes.next = leaked_tokens-adj_token



    @always_comb
    def currToken():
        tmp_1 = modbv(0)[bucket_w:0]
        tmp_1_of = modbv(0)[bucket_w:0]
        tmp_2 = modbv(0)[bucket_w:0]
        if mmd_mode[0] == 0:
            if itoken_1 + sply_token_1 > cap_1:
                tmp_1[:] = cap_1
                tmp_1_of[:] = itoken_1 + sply_token_1 - cap_1
            else:
                tmp_1[:] = itoken_1 + sply_token_1
            if itoken_2 + tmp_1_of > cap_2:
                tmp_2[:] = cap_2
            else:
                tmp_2[:] = itoken_2 + tmp_1_of

            if entry_reset == 1:
                tmp_1[:] = cap_1
                tmp_2[:] = cap_2
                
            
            if mmd_mode[1] == 0:
                # color aware srTCM
                if tmp_1 >= adj_bytes and icolor==GREEN:
                    new_token_1.next = tmp_1-adj_bytes
                    new_token_2.next = tmp_2
                    new_color.next = GREEN
                elif (icolor==GREEN or icolor==YELLOW) and tmp_2 >= adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = YELLOW
                else:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2
                    new_color.next = RED
            else:
                # color blind srTCM
                if tmp_1 >= adj_bytes:
                    new_token_1.next = tmp_1-adj_bytes
                    new_token_2.next = tmp_2
                    new_color.next = GREEN
                elif tmp_2 >= adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = YELLOW
                else:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2
                    new_color.next = RED

        else:
            if itoken_1 + sply_token_1 > cap_1:
                tmp_1[:] = cap_1
            else:
                tmp_1[:] = itoken_1 + sply_token_1
            if itoken_2 + sply_token_2 > cap_2:
                tmp_2[:] = cap_2
            else:
                tmp_2[:] = itoken_2 + sply_token_2
            
            if mmd_mode[1] == 0:
                # color aware trTCM
                if icolor == RED or tmp_2<adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2
                    new_color.next = RED
                elif icolor == YELLOW or tmp_1<adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = YELLOW
                else:
                    new_token_1.next = tmp_1-adj_bytes
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = GREEN
            else:
                # color blind trTCM
                if tmp_2<adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2
                    new_color.next = RED
                elif tmp_1<adj_bytes:
                    new_token_1.next = tmp_1
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = YELLOW
                else:
                    new_token_1.next = tmp_1-adj_bytes
                    new_token_2.next = tmp_2-adj_bytes
                    new_color.next = GREEN
                
    
    # If MMD is not valid, return the original color and no drop
    @always_comb
    def getColorDrop():
        if read_done==1:
            odrop_d0.next  = drop_mode[new_color]
            ocolor_d0.next = new_color
        else:
            odrop_d0.next = idrop
            ocolor_d0.next = icolor

    # Output pipeline
    zPipToken1  = multiflop(new_token_1, otoken_1, clk, rstn, depth = algo_latency)
    zPipToken2  = multiflop(new_token_2, otoken_2, clk, rstn, depth = algo_latency)    
    zPipDrop    = multiflop(odrop_d0, odrop, clk, rstn, depth = algo_latency)
    zPipColor   = multiflop(ocolor_d0, ocolor, clk, rstn, depth = algo_latency)    
    


    return instances()
    
    
    
    
    
        


    
