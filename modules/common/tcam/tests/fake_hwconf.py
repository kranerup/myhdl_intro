import sys


class hwconf:
    nr_of_id = 32
    nr_of_pb = 2
    start_address_space = 0
    conf_data_width = 64
    sparsly_table_address_space = False
    maximum_address_space = 0x8000_0000
    conf_collector_inp_flops = False
    conf_collector_combinational = False
    conf_bus_collector_output_flops = []
    block_conf_flops = 1
    conf_interface = None
    conf_addr_width = 32
    table_addresses = None
    register_holes = None
    # cam_model = "default"
    # cam_model = "cavium"

    def regTab_check_exist_address(self, address):
        return False

    def regTab_check_extra_address_space(self, address):
        return False

    def __init__(self):
        self.hwconf = self

    def create_hwconf(self):
        pass

    eme_config = dict(
        ports=[12],
        port_bw=20000,
        nr_of_queues=64,
        axi_data_width=128,
        axi_addr_width=40,
        debug_port=4,
        per_queue_statistics=True,
    )

    def __getattr__(self, _):
        return None


sys.modules["settings.hwconf"] = hwconf()
