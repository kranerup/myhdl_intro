from myhdl import *
from modules.common.Common import copySignal, pipeline, pass_through, multiflop
import sys
from modules.common.Common import hwdir, compoundWidth, listType, signalType

zPsFold = []
zPsUnFold = []
class info_if():
    def __init__(self,interface,
                 pac_defs = {},
                 name = '',
                 **kwarg):

        #
        
        self.hwconf = kwarg['hwconf']
        
        self.interface = interface
        self.name = interface + name

        self.external = True
        if "port" in kwarg:            
            self.port = kwarg['port']
            self.external = not self.port in self.hwconf.internal_ports
        else:
            self.port = None
            
        if interface == 'datasheet':
            yml_path = '../'
        else:
            yml_path = None
            
        pac_defs      = self.hwconf.defines

        if 'nr_of_id' in kwarg:
            nr_of_id = kwarg['nr_of_id']
        else:
            nr_of_id = 1

        """
        Current info locations:
        ---
        tb_rx
        rx_sp
        ipp_pb
        pb_epp
        eppp_in
        eppp_bypass
        eppp_out
        eppp_pm
        epp_ps
        ps_tx
        tx_tb
        datasheet
        """
            

        self.rx_doc         = [] # Names on RX interface for the datasheet
        self.tx_doc         = [] # Names on TX interface for the datasheet
        self.tx_halt_doc    = []
        
        self.stimuli_list    = [] # Info bus from the stimuli
        self.scoreboard_list = [] # Info bus to the scoreboard

        # Info interface between mac wrapper and sp        
        self.rx_sp_list  = [] 
        self.rx_sp_name  = []

        # Info interface between sp wrapper and ipp
        self.sp_ipp_list  = [] 
        self.sp_ipp_name  = []


        # Info interface between ingress common and ipm
        self.ic_ipm_list = []
        self.ic_ipm_name = []
        
        # Info interface between ipp and pb        
        self.ipp_pb_list = []
        self.ipp_pb_name = []

        # Info interface between pb and epp        
        self.pb_epp_list = []
        self.pb_epp_name = []

        ###############################################################
        # Info around EPPP
        # stdlib.pah has a corresponding structure for eppp input info
        self.eppp_in_list = [] # [0] is the first item in pac struct
        self.eppp_in_name = []

        # stdlib.pah has a corresponding structure for eppp output info
        self.eppp_out_list = [] # [0] is the first item in pac struct
        self.eppp_out_name = []
        ###############################################################

        # Implict pipeline in EPPP
        self.eppp_bypass_list = []
        self.eppp_bypass_name = []

        # Info interface between eppp and pm
        self.eppp_pm_list  = []
        self.eppp_pm_name  = []

        # Info interface between epp and ps        
        self.epp_ps_list = []
        self.epp_ps_name = []

        # Info interface between ps and mac wrapper        
        self.ps_tx_list  = []
        self.ps_tx_name  = []


        # Info interface between tb and dut rx
        self.tb_rx_list  = []
        self.tb_rx_name  = []

        
        # Info interface between dut tx and tb
        self.tx_tb_list  = []
        self.tx_tb_name  = []

        
        self.tx_halt_info_width = 0 # Width of info interface between mac_wrapper and ps, used by halt

        # All kinds of info signals
        
        ############################################################


        ############################################################

        # PTP default
        self.ptp = None
        self.upd_ts = None
        self.upd_cf = None
        self.ts_to_sw = None
        self.ts = None
        self.udp4 = None
        self.udp6 = None
        self.udp_csum = None
        self.ts_pos = None            
        self.udp_corr = None
        self.valid_ts = None

        if self.hwconf.ptp_mode:

            self.ptp = Signal(intbv(0)[1:0])
            #self.eppp_out_list.append(self.ptp)
            
            if self.hwconf.only_cell_mode:
                self.tx_doc.append('ptp')
                self.eppp_out_list.append(self.ptp)
                self.eppp_out_name.append('ptp')
            else:
                epp_params = self.hwconf.ppp_params['e'][0]
                pos_width = epp_params['port_width']['ovalid_bytes']

                if self.hwconf.ptp_mode=="2_step":
                    self.upd_ts = Signal(intbv(0)[1:0])
                    ptp_sig_list = [self.upd_ts]
                    ptp_name_list = ['upd_ts']
                    ptp_doc_list = [r'upd\_ts']

                else:
                    
                    self.upd_ts = Signal(intbv(0)[1:0])
                    self.upd_cf = Signal(intbv(0)[1:0])
                    self.ts_to_sw = Signal(intbv(0)[1:0])
                    self.ts   = Signal(intbv(0)[pac_defs['c_TIMESTAMP_SIZE']*8:0])
                    self.udp4 = Signal(intbv(0)[1:0])
                    self.udp6 = Signal(intbv(0)[1:0])
                    self.udp_csum = Signal(intbv(0)[pos_width:0])
                    self.ts_pos = Signal(intbv(0)[pos_width:0])
                    self.udp_corr = Signal(intbv(0)[self.hwconf.pkt_length_w:0])

                    ptp_sigs = [
                        # signal,            sig_name,         doc_name
                        # this is directly from the t_ptp_to_mac struct in egress pac
                        ( self.upd_ts,       'upd_ts',         r'upd\_ts'    ),  # lsb
                        ( self.upd_cf,       'upd_cf',         r'upd\_cf'    ), 
                        ( self.ts_to_sw,     'ts_to_sw',       r'ts\_to\_sw' ),
                        ( self.ts,           'ts',             'ts'          ),
                        ( self.udp4,         'udp4',           'udp4',       ), 
                        ( self.udp6,         'udp6',           'udp6',       ), 
                        ( self.udp_csum,     'udp_csum',       r'udp\_csum', ), 
                        ( self.ts_pos,       'ts_pos',         r'ts\_pos',   ), 
                        ( self.udp_corr,     'udp_corr',       r'udp\_corr', ), 
                    ]

                    ptp_sig_list  = [ item[0] for item in ptp_sigs ]
                    ptp_name_list = [ item[1] for item in ptp_sigs ]
                    ptp_doc_list  = [ item[2] for item in ptp_sigs ]

                self.tx_doc += ptp_doc_list

                self.eppp_out_list += ptp_sig_list
                self.eppp_out_name += ptp_name_list

                self.eppp_pm_list += ptp_sig_list
                self.eppp_pm_name += ptp_name_list

                self.epp_ps_list += ptp_sig_list
                self.epp_ps_name += ptp_name_list

                self.ps_tx_list += ptp_sig_list
                self.ps_tx_name += ptp_name_list

                self.tx_tb_list += ptp_sig_list
                self.tx_tb_name += ptp_name_list


                if interface in ('rx_doc', 'tb_rx', 'rx_sp', 'sp_ipp', 'ipp_pb', 'pb_epp', 'eppp_in'):
                    if self.hwconf.rx_ptp_if:

                        self.valid_ts = Signal(intbv(0)[1:0])
                        self.ts  = Signal(intbv(0)[pac_defs['c_TIMESTAMP_SIZE']*8:0])                    

                        self.rx_doc.append('valid\_ts')
                        self.rx_doc.append('ts')

                        self.tb_rx_list.append(self.valid_ts)
                        self.tb_rx_list.append(self.ts)
                        self.tb_rx_name.append('valid_ts')
                        self.tb_rx_name.append('ts')        

                        self.rx_sp_list.append(self.valid_ts)
                        self.rx_sp_list.append(self.ts)
                        self.rx_sp_name.append('valid_ts')
                        self.rx_sp_name.append('ts')          

                        self.sp_ipp_list.append(self.valid_ts)
                        self.sp_ipp_name.append('valid_ts')
                        self.sp_ipp_list.append(self.ts)
                        self.sp_ipp_name.append('ts')          


                        self.ipp_pb_list.append(self.valid_ts)
                        self.ipp_pb_name.append('valid_ts')
                        self.ipp_pb_list.append(self.ts)
                        self.ipp_pb_name.append('ts')

                        self.pb_epp_list.append(self.valid_ts)
                        self.pb_epp_name.append('valid_ts')
                        self.pb_epp_list.append(self.ts)
                        self.pb_epp_name.append('ts')

                        self.eppp_in_list.append(self.valid_ts)
                        self.eppp_in_name.append('valid_ts')
                        self.eppp_in_list.append(self.ts)
                        self.eppp_in_name.append('ts')
                    
                    else:
                        self.valid_ts = None
                        self.ts  = None
                    
                
        
        ############################################################

        # Pkt length mac mode
        if self.hwconf.pkt_length_mac_mode:
            self.tx_doc.append('pkt\_length')            

        ############################################################

        # Pkt length
        if '_TUNNELING' in pac_defs:
            tunneling = 1
        else:
            tunneling = 0

        if '_EXTENDED_TO_CPU_TAG' in pac_defs:
            extended_to_cpu_tag = 1
        else:
            extended_to_cpu_tag = 0
            
            
        if (self.hwconf.ptp_mode or self.hwconf.pkt_length_mode or self.hwconf.pkt_length_mac_mode or tunneling):
            self.pkt_length = Signal(intbv(0)[self.hwconf.pkt_length_w:0])

            self.pb_epp_list.append(self.pkt_length)
            self.pb_epp_name.append('pkt_length')
            
            self.eppp_bypass_list.append(self.pkt_length)
            self.eppp_bypass_name.append('pkt_length')

            if self.hwconf.ptp_mode or extended_to_cpu_tag or tunneling:
                self.eppp_in_list.append(self.pkt_length)
                self.eppp_in_name.append('pkt_length')

            if self.hwconf.pkt_length_mac_mode:
                self.eppp_pm_list.append(self.pkt_length)
                self.eppp_pm_name.append('pkt_length')
                
                self.epp_ps_list.append(self.pkt_length)
                self.epp_ps_name.append('pkt_length')
                
                self.ps_tx_list.append(self.pkt_length)
                self.ps_tx_name.append('pkt_length')

                self.tx_tb_list.append(self.pkt_length)
                self.tx_tb_name.append('pkt_length')
                
            elif interface in ('epp_ps', 'ps_tx', 'tx_tb'):
                self.pkt_length = None

        else:
            self.pkt_length = None

        ############################################################            
        
        # Express
        if self.hwconf.express_mode:
            self.rx_doc.append('express')
            self.tx_doc.append('express')
            self.express = Signal(intbv(0)[1:0])

            self.tb_rx_list.append(self.express)
            self.tb_rx_name.append('express')
            
            self.rx_sp_list.append(self.express)
            self.rx_sp_name.append('express')

            self.pb_epp_list.append(self.express)
            self.pb_epp_name.append('express')

            self.eppp_bypass_list.append(self.express)
            self.eppp_bypass_name.append('express')
            
            # Not in eppp_pm, PM needs express bit

            self.epp_ps_list.append(self.express)
            self.epp_ps_name.append('express')
            
            self.ps_tx_list.append(self.express)
            self.ps_tx_name.append('express')

            self.tx_tb_list.append(self.express)
            self.tx_tb_name.append('express')
            

            self.tx_halt_info_width += 1
        else:
            self.express = None
        
        ############################################################

        # Port group sub_id
        if nr_of_id > 1:
            self.rx_doc.append('sub\_id')
            self.tx_doc.append('sub\_id')
            self.sub_id = Signal(intbv(0, min=0, max=nr_of_id))
            
            self.rx_sp_list.append(self.sub_id)
            self.rx_sp_name.append('sub_id')
            
            self.ps_tx_list.append(self.sub_id)
            self.ps_tx_name.append('sub_id')
            
        else:
            self.sub_id = None
        
        ############################################################

        # Prio mode
        if self.hwconf.prio_mode:
            self.tx_doc.append('prio')
            self.prio = Signal(intbv(0, min=0, max=self.hwconf.nr_of_prios))

            self.pb_epp_list.append(self.prio)
            self.pb_epp_name.append('prio')

            self.eppp_bypass_list.append(self.prio)
            self.eppp_bypass_name.append('prio')
            
            self.eppp_pm_list.append(self.prio)
            self.eppp_pm_name.append('prio')
            
            self.epp_ps_list.append(self.prio)
            self.epp_ps_name.append('prio')
            
            self.ps_tx_list.append(self.prio)
            self.ps_tx_name.append('prio')

            self.tx_tb_list.append(self.prio)
            self.tx_tb_name.append('prio')
            
        else:
            self.prio = None
            
        ############################################################

        # MMP
        if '_COLORING' in pac_defs:
            self.color = Signal(intbv(0)[2:0])

            if pac_defs['c_TOP_MMP'] > 0:            
                self.ic_ipm_list.append(self.color)
                self.ic_ipm_name.append('color')
            
            self.ipp_pb_list.append(self.color)
            self.ipp_pb_name.append('color')

            self.pb_epp_list.append(self.color)
            self.pb_epp_name.append('color')
            
            self.eppp_in_list.append(self.color)
            self.eppp_in_name.append('color')
            
        else:
            self.color = None


        self.eop_drop_mask = None
        if 'c_TOP_MMP' in pac_defs:
            if pac_defs['c_TOP_MMP'] > 0:
                self.eop_drop_mask = Signal(intbv(0)[self.hwconf.nr_of_ports:0])
                
                self.ic_ipm_list += [self.eop_drop_mask]
                self.ic_ipm_name += ['eop_drop_mask']

        # Congest port & pkt age
        if self.hwconf.pkt_age_config != None:
            # {timestamp, tick_nr}
            self.agestamp = Signal(intbv(0)[self.hwconf.pkt_age_config['width']:0])
            
            self.ipp_pb_list.append(self.agestamp)
            self.ipp_pb_name.append('age_stamp')

            self.pb_epp_list.append(self.agestamp)
            self.pb_epp_name.append('age_stamp')

            
            tick_w = (self.hwconf.tick['nr_of_ticks']-1).bit_length()            
            tick_cnt_w = self.hwconf.pkt_age_config['width'] - tick_w
            self.pkt_delay = Signal(modbv(0)[tick_cnt_w:0])

            self.eppp_in_list.append(self.pkt_delay)
            self.eppp_in_name.append('pkt_delay')
        else:
            self.agestamp = None            
            self.pkt_delay = None
            

        ############################################################
        # 
        ############################################################
        # info signals based on interface locations
        if interface == 'tb_rx':
            self.info_list = self.tb_rx_list
            self.name_list = self.tb_rx_name
        elif interface == 'rx_sp':
            self.info_list = self.rx_sp_list
            self.name_list = self.rx_sp_name
        elif interface == 'sp_ipp':
            self.info_list = self.sp_ipp_list
            self.name_list = self.sp_ipp_name
        elif interface == 'ic_ipm':
            self.info_list = self.ic_ipm_list
            self.name_list = self.ic_ipm_name
        elif interface == 'ipp_pb':
            self.info_list = self.ipp_pb_list
            self.name_list = self.ipp_pb_name
        elif interface == 'pb_epp':
            self.info_list = self.pb_epp_list
            self.name_list = self.pb_epp_name
        elif interface == 'eppp_in':
            self.info_list = self.eppp_in_list
            self.name_list = self.eppp_in_name
        elif interface == 'eppp_bypass':

            if self.hwconf.re_queue:
                self.eppp_bypass_list.append(kwarg['reque'])
                self.eppp_bypass_name.append('reque')
            
            # Always exist
            epp_dest_id     = kwarg['dest_id']
            epp_last        = kwarg['last']
            epp_dest_queue  = kwarg['dest_queue']
            epp_valid_bytes = kwarg['valid_bytes']

            self.eppp_bypass_list += [epp_dest_id, epp_last, epp_dest_queue, epp_valid_bytes]
            self.eppp_bypass_name += ['dest_id', 'last', 'dest_queue', 'valid_bytes']


            self.info_list = self.eppp_bypass_list
            self.name_list = self.eppp_bypass_name
            
        
            
        elif interface == 'eppp_out':
            self.info_list = self.eppp_out_list
            self.name_list = self.eppp_out_name
        elif interface == 'eppp_pm':
            self.info_list = self.eppp_pm_list
            self.name_list = self.eppp_pm_name
        elif interface == 'epp_ps':
            self.info_list = self.epp_ps_list
            self.name_list = self.epp_ps_name
        elif interface == 'ps_tx':
            self.info_list = self.ps_tx_list
            self.name_list = self.ps_tx_name
        elif interface == 'tx_tb':
            self.info_list = self.tx_tb_list
            self.name_list = self.tx_tb_name
        elif interface == 'datasheet':
            self.info_list = None
            self.name_list = None
        else:
            print('info_if: ERROR! Unknown interface', interface)
            assert False

        if self.info_list != None:
            self.info_w = compoundWidth(self.info_list)
        else:
            self.info_w = 0

        print("%s: Instantiated info bus with %s"%(self.interface, self.name_list))

        
        if 'info' in kwarg and kwarg['info'] != None:
            if len(kwarg['info']) != self.info_w:
                print("%s: ERROR! info width mismatch"%self.interface)
                assert False
            self.info = kwarg['info']
        else:
            if self.info_w > 0:
                self.info  = Signal(intbv(0)[self.info_w:0])
            else:
                self.info = None
                self.info_list  = []


    def fold(self, info_list=None, info=None, name=""):
        # Encode the signal list to a flattened signal
        if info_list==None:
            # Not working
            print("IO needs to be specified", self.interface)
            assert False
            # zPsFold = pass_through(self.info_list, self.info,name = name+'.psFold')
        elif info != None:            
            # If the module has multiple fold, the ports need to be specified externally
            zPsFold = pass_through(info_list, self.info, name = name+'.psFold')            
        
        return instances()

    def unfold(self,info=None,info_list=None, name=""):
        # Decode the flattened signal to the signal list
        if info_list == None:
            # Not working
            print("IO needs to be specified", self.interface)
            assert False
            # zPsUnFold = pass_through(self.info, self.info_list,name=name+'.psUnFold')
        elif info != None:
            # If the module has multiple unfold, the ports need to be specified externally
            zPsUnFold = pass_through(info, info_list, name=name+'.psUnFold')

        return instances()
        

    def bind(self,src, info_list, fold=False):        
        # Bind from another info list to the current one, matching signals by names
        # By default bind to each signal in the bundle, and can be folded optionally

        # info_list is self.info_list, need to be in the attribute otherwise the name hierarchy is strange
        
        zPsField = []
        if self.info_list != None:
            for i in range(len(self.info_list)):
                name = self.name_list[i]
                if name in src.name_list:
                    source_idx = src.name_list.index(name)
                    zPsField.append(pass_through(src.info_list[source_idx], info_list[i], name=self.interface+'.bind%s'%name ))

            if fold:
                zPsFold = self.fold(info_list, self.info, name='bindFold')            

            
        # if iinfo.info != None:
        #     zPsField = []
        #     for i in range(len(self.info_list)):
        #         name = self.name_list[i]
        #         if iinfo!=None and name in iinfo.name_list:
        #             source_idx = iinfo.name_list.index(name)
        #             zPsField.append(pass_through(iinfo.info_list[source_idx], self.info_list[i],name=self.interface+'.bind%s'%name ))
        #         elif name in kwarg:
        #             zPsField.append(pass_through(kwarg[name], self.info_list[i],name=self.interface+'.bind%s'%name ))
        #         else:
        #             print "%s in %s is not driven by auto binding and needs to be assigned manually"%(name,self.interface)

        #     if fold:
        #         zPsFold = self.fold(self.info_list,self.info,name='bindFold')

        return instances()
                
        

