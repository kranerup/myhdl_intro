`timescale 1ns/10ps

///////////////////////////////////////////////////////
//
// This is a simple behavioral model of the xilinx block mem
// macro, ment to be used for simulating outside of vivado. Not for synthesis

// The parameters are from the 2024.2 template, but it works for some earlier versions
// as well (tested for 2021.1) because the parameters are a superset.

module behav_xpm_memory_sdpram(
                         dbiterrb,
                         doutb,
                         sbiterrb,
                         addra,
                         addrb,
                         clka,
                         clkb,
                         dina,
                         ena,
                         enb,
                         injectdbiterra,
                         injectsbiterra,
                         regceb,
                         rstb,
                         sleep,
                         wea
		      );
   parameter ADDR_WIDTH_A = 6;
   parameter ADDR_WIDTH_B = 6;
   parameter AUTO_SLEEP_TIME = 0;
   parameter BYTE_WRITE_WIDTH_A = 32;
   parameter CASCADE_HEIGHT = 0;
   parameter CLOCKING_MODE = "common_clock";
   parameter ECC_BIT_RANGE = "7:0";
   parameter ECC_MODE = "no_ecc";
   parameter ECC_TYPE = "none";
   parameter IGNORE_INIT_SYNTH = 0;
   parameter MEMORY_INIT_FILE = "none";
   parameter MEMORY_INIT_PARAM = "0";
   parameter MEMORY_OPTIMIZATION = "true";
   parameter MEMORY_PRIMITIVE = "block";
   parameter MEMORY_SIZE = 2048;
   parameter MESSAGE_CONTROL = 0;
   parameter RAM_DECOMP = "auto";
   parameter READ_DATA_WIDTH_B = 32;
   parameter READ_LATENCY_B = 2;
   parameter READ_RESET_VALUE_B = "0";
   parameter RST_MODE_A = "SYNC";
   parameter RST_MODE_B = "SYNC";
   parameter SIM_ASSERT_CHK = 0;
   parameter USE_EMBEDDED_CONSTRAINT = 0;
   parameter USE_MEM_INIT = 0;
   parameter USE_MEM_INIT_MMI = 0;
   parameter WAKEUP_TIME = "disable_sleep";
   parameter WRITE_DATA_WIDTH_A = 32;
   parameter WRITE_MODE_B = "read_first";
   parameter WRITE_PROTECT = 1;
   
   output dbiterrb;
   output [READ_DATA_WIDTH_B-1:0] doutb;
   output sbiterrb;
   input [ADDR_WIDTH_A-1:0] addra;
   input [ADDR_WIDTH_B-1:0] addrb;
   input clka;
   input clkb;
   input [WRITE_DATA_WIDTH_A-1:0] dina;
   input ena;
   input enb;
   input injectdbiterra;
   input injectsbiterra;
   input regceb;
   input rstb;
   input sleep;
   input wea;

   generate 
      if( CLOCKING_MODE == "common_clock" ) begin
         verilog_memory_fpga #(
                               .width(READ_DATA_WIDTH_B),
                               .depth(MEMORY_SIZE/READ_DATA_WIDTH_B),
                               .depth_w($clog2(MEMORY_SIZE/READ_DATA_WIDTH_B)),
                               .mask_w(1),
                               .pre_load(1),
                               .reset_value(0),
                               .write_through(0),
                               .input_flops(0),
                               .output_flops(READ_LATENCY_B-1)
                               )
         vminst(
                .idata(   dina ),
	        .odata(   doutb ),
	        .waddr(   addra ),
	        .raddr(   addrb ),
	        .wenable( ena),
                .wmask(   1'b1 ),
	        .renable( enb ),
	        .clk(     clka )
                );
      end else begin // if ( CLOCKING_MODE == "common_clock" )
         verilog_memory_2c_fpga #(
                               .width(READ_DATA_WIDTH_B),
                               .depth(MEMORY_SIZE/READ_DATA_WIDTH_B),
                               .depth_w($clog2(MEMORY_SIZE/READ_DATA_WIDTH_B)),
                               .pre_load(1),
                               .reset_value(0),
                               .input_flops(0),
                               .output_flops(READ_LATENCY_B-1)
                               )
         vminst(
                .idata(   dina ),
	        .odata(   doutb ),
	        .waddr(   addra ),
	        .raddr(   addrb ),
	        .wenable( ena),
	        .renable( enb ),
	        .rclk(    clkb ),
	        .wclk(    clka )
                );
      end // else: !if( CLOCKING_MODE == "common_clock" )
   endgenerate
   
endmodule
