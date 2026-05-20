`timescale 1ns/10ps

`ifndef membus_out_width
  `define membus_out_width 2
  `define membus_in_width 2
`endif

module verilog_memory_nodft(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
                      wmask,
		      renable,
		      clk,
		      rstn
		      );

   parameter width = 1;         // The memory width in bits
   parameter depth = 1;         // The memory depth
   parameter depth_w = 1;       // The memory address width
   parameter mask_w = 1;
   parameter pre_load = 0;      // If set to one the memory will be initialized with
                                // "reset_value" (to speed up simulations)
   parameter reset_value = 0;   // The value loaded in the memory if pre_load is set
   parameter write_through = 0; // When set: Simultaneous reading and writing to the 
                                // same address produces the newly written data as
                                // read data
   parameter input_flops = 0;
   parameter output_flops = 0;

   parameter wgran = width / mask_w;

   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input [mask_w-1:0]  wmask;
   input 	       renable;
   input 	       clk;
   input 	       rstn;

   wire [`membus_in_width-1:0] dft_out;
   
   verilog_memory #(
                    .width(width),
                    .depth(depth),
                    .depth_w(depth_w),
                    .mask_w(mask_w),
                    .pre_load(pre_load),
                    .reset_value(reset_value),
                    .write_through(write_through),
                    .input_flops(input_flops),
                    .output_flops(output_flops))
   vmeminst(
           .idata(idata),
           .odata(odata),
           .waddr(waddr),
           .raddr(raddr),
           .wenable(wenable),
           .wmask(wmask),
           .renable(renable),
           .clk(clk),
           .rstn(rstn),
           .dft_in(`membus_in_width'b0),
           .dft_out(dft_out)
            );
endmodule // verilog_memory_nodft
