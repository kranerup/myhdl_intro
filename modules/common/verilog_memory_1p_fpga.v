`timescale 1ns/10ps

module verilog_memory_1p_fpga_ff(i, o, clk);
   parameter w = 1;
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;

   reg    [w-1:0] o;
   
   always @(posedge clk) begin
      o <= i;
   end
endmodule
   
module verilog_memory_1p_fpga_pipe(i,o,clk);
   parameter w = 1;
   parameter d = 1; // Only 0 and 1 supported, for now.
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;
   
   generate
      if (d == 0) begin
         assign o = i;
      end else begin
         verilog_memory_1p_fpga_ff #(.w(w) ) flop(i, o, clk);
      end
   endgenerate
   
endmodule // pipe

   
module verilog_memory_1p_fpga(
		      idata,
		      odata,
		      addr,
		      enable,
		      wenable,
		      clk
		      );
   
   parameter width = 1;         // The memory width in bits
   parameter depth = 1;         // The memory depth
   parameter depth_w = 1;       // The memory address width
   parameter pre_load = 0;      // If set to one the memory will be initialized with "reset_value" (to speed up simulations)
   parameter reset_value = 0;   // The value loaded in the memory if pre_load is set
   parameter input_flops = 0;
   parameter output_flops = 0;
   
   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] addr;
   input 	       enable;
   input 	       wenable;
   input 	       clk;

   wire [width-1:0]    idata_i;
   wire [depth_w-1:0]  addr_i;
   wire                enable_i;
   wire                wenable_i;
                           
   reg [width-1:0]     odata_i;
      
   wire [width-1:0] odata;
   reg [width-1:0]  data [0:depth-1];
  
   verilog_memory_1p_fpga_pipe #(.w(1),       .d(input_flops))  flopre(.i(enable),  .o(enable_i),  .clk(clk));
   verilog_memory_1p_fpga_pipe #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(clk));
   verilog_memory_1p_fpga_pipe #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(clk));
   verilog_memory_1p_fpga_pipe #(.w(depth_w), .d(input_flops))  flopra(.i(addr),    .o(addr_i),    .clk(clk));
   verilog_memory_1p_fpga_pipe #(.w(width),   .d(output_flops)) flopod(.i(odata_i), .o(odata),     .clk(clk));
   
   always @(posedge clk) begin
      if (enable_i == 1 && wenable_i == 0) begin
	 odata_i <= data[addr_i];
      end
      if (enable_i == 1 && wenable_i == 1) begin
         data[addr_i] <= idata_i;
      end
   end

   generate
      if (pre_load==1) begin
	 integer i;
	 initial begin
	    for (i=0; i<depth; i=i+1) begin
               data[i] = reset_value;
	    end
	 end
      end
   endgenerate
   
endmodule // verilog_memory_1p_fpga

