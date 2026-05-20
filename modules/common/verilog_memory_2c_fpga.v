`timescale 1ns/10ps

module verilog_memory_2c_fpga_ff(i, o, clk);
   parameter w = 1;
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;

   reg    [w-1:0] o;
   
   always @(posedge clk) begin
      o <= i;
   end
endmodule
   
module verilog_memory_2c_fpga_pipe(i,o,clk);
   parameter w = 1;
   parameter d = 1; // Only 0 and 1 supported, for now.
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;
   
   generate
      if (d == 0) begin
         assign o = i;
      end else begin
         verilog_memory_2c_fpga_ff #(.w(w) ) flop(i, o, clk);
      end
   endgenerate
   
endmodule // pipe

   
module verilog_memory_2c_fpga(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
		      renable,
		      rclk,
		      wclk
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
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input 	       renable;
   input 	       rclk;
   input 	       wclk;

   wire [width-1:0]    idata_i;
   wire [depth_w-1:0]  raddr_i;
   wire [depth_w-1:0]  waddr_i;
   wire                wenable_i;
   wire                renable_i;
                           
   reg [width-1:0]     odata_i;
      
   wire [width-1:0] odata;
   reg [width-1:0]  data [0:depth-1];
  
   generate
      if (input_flops>0) begin
         verilog_memory_2c_fpga_pipe #(.w(1),       .d(input_flops))  flopre(.i(renable), .o(renable_i), .clk(rclk));
         verilog_memory_2c_fpga_pipe #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(wclk));
         verilog_memory_2c_fpga_pipe #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(wclk));
         verilog_memory_2c_fpga_pipe #(.w(depth_w), .d(input_flops))  flopra(.i(raddr),   .o(raddr_i),   .clk(rclk));
         verilog_memory_2c_fpga_pipe #(.w(depth_w), .d(input_flops))  flopwa(.i(waddr),   .o(waddr_i),   .clk(wclk));
      end else begin
         assign renable_i = renable;
         assign wenable_i = wenable;
         assign idata_i   = idata;
         assign raddr_i   = raddr;
         assign waddr_i   = waddr;
      end // else: !if(input_flops>0)
      if (output_flops>0) begin
         verilog_memory_2c_fpga_pipe #(.w(width),   .d(output_flops)) flopod(.i(odata_i), .o(odata),     .clk(rclk));
      end else begin
         assign odata = odata_i;
      end
   endgenerate
   
   always @(posedge rclk) begin
      if (renable_i == 1) begin
	 odata_i <= data[raddr_i];
      end
   end
   always @(posedge wclk) begin
      if (wenable_i == 1) begin
         data[waddr_i] <= idata_i;
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

endmodule // verilog_memory_2c_fpga
