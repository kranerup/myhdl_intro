`timescale 1ns/10ps

`ifndef membus_out_width
  `define membus_out_width 2
`endif
`ifndef membus_in_width
  `define membus_in_width 2
`endif
`ifndef pktarc_xpm_memory_sdpram
  `define pktarc_xpm_memory_sdpram xpm_memory_sdpram
`endif

///////////////////////////////////////////////////////
//
// verilog_memory_2c_xilinx_ecc instanciates block ram (or ultra ram)
// with ECC for dual clock memories. It uses the same primitives as verilog_memory_xilinx_ecc

module verilog_memory_2c_xilinx_ecc(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
                      wmask,
		      renable,
		      rclk,
		      wclk,
                      rstn,
                      dft_in,
                      dft_out
		      );

   parameter width = 1;         // The memory width in bits
   parameter depth = 1;         // The memory depth
   parameter depth_w = 1;       // The memory address width
   parameter mask_w = 1;      
   parameter pre_load = 0;      // If set to one the memory will be initialized with
                                // "reset_value" (to speed up simulations)
   parameter reset_value = 0;   // Note that XPM memories with ECC do not support reset_values other than 0
   parameter write_through = 0; // When set: Simultaneous reading and writing to the 
                                // same address produces the newly written data as
                                // read data
   parameter input_flops = 0; 
   parameter output_flops = 0;

   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input [mask_w-1:0]  wmask;
   input 	       renable;
   input 	       rclk;
   input 	       wclk;
   input 	       rstn;
   input [`membus_in_width-1:0] dft_in;
   output [`membus_out_width-1:0] dft_out;

   wire [width-1:0]    idata_i;
   wire [depth_w-1:0]  raddr_i;
   wire [depth_w-1:0]  waddr_i;
   wire                wenable_i;
   wire                renable_i;

   wire [width-1:0]     odata_i;

   reg [width-1:0]  odata;
   reg [width-1:0]  idata_d1, idata_dd;
   reg 		    collision, collision_d1, collision_dd;

   generate
      if (input_flops > 0) begin
         verilog_memory_pipe_xilinx_ecc #(.w(1),       .d(input_flops))  flopre(.i(renable), .o(renable_i), .clk(rclk));
         verilog_memory_pipe_xilinx_ecc #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(wclk));
         verilog_memory_pipe_xilinx_ecc #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(wclk));
         verilog_memory_pipe_xilinx_ecc #(.w(depth_w), .d(input_flops))  flopra(.i(raddr),   .o(raddr_i),   .clk(rclk));
         verilog_memory_pipe_xilinx_ecc #(.w(depth_w), .d(input_flops))  flopwa(.i(waddr),   .o(waddr_i),   .clk(wclk));
      end else begin
         assign renable_i = renable;
         assign wenable_i = wenable;
         assign idata_i   = idata;
         assign raddr_i   = raddr;
         assign waddr_i   = waddr;
      end
      if (output_flops > 0) begin
         verilog_memory_pipe_xilinx_ecc #(.w(width),   .d(output_flops)) flopod(.i(odata_i), .o(odata),     .clk(rclk));
      end else begin
         assign odata     = odata_i;
      end
   endgenerate

   xilinx_ecc_block_memory #(
                             .width(width),
                             .depth(depth),
                             .depth_w(depth_w),
                             .output_flops(output_flops),
                             .reset_value(reset_value),
                             .dual_clock(1'b1)
                             )
   eccmeminst(
              .idata(idata_i),
              .odata(odata_i),
              .waddr(waddr_i),
              .raddr(raddr_i),
              .wenable(wenable_i),
              .renable(renable_i),
              .rclk(rclk),
              .wclk(wclk),
              .rstn(rstn),
              .dft_in(dft_in),
              .dft_out(dft_out)                 
              );
   
   
endmodule // verilog_memory_2c_xilinx_ecc

