`timescale 1ns/10ps


///////////////////////////////////////////////////////
//
// verilog_memory_fpga differs from verilog_memory in that
// in that the code is written so that vivado can merge the output
// registers into the block RAM macros. The changes from the vanilla
// variant is that the output flop is not reset, and the collision
// logic is after the output flop. This also means that the input data
// has to be pipelined an additional stage, so there is no savings in
// flops for the write_through mode. But the timing is likely better.

module verilog_memory_ff_fpga(i, o, clk);
   parameter w = 1;
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;

   reg    [w-1:0] o;
   initial o = 0;
   
   always @(posedge clk) begin
      o <= i;
   end
endmodule

module verilog_memory_pipe_fpga(i,o,clk);
   parameter w = 1;
   parameter d = 1; // Only 0 and 1 supported, for now.
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;

   generate
      if (d == 0) begin
         assign o = i;
      end else begin
         verilog_memory_ff_fpga #(.w(w) ) flop(i, o, clk);
      end
   endgenerate

endmodule // pipe


module verilog_memory_fpga(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
                      wmask,
		      renable,
		      clk
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

   wire [width-1:0]    idata_i;
   wire [depth_w-1:0]  raddr_i;
   wire [depth_w-1:0]  waddr_i;
   wire                wenable_i;
   wire                renable_i;

   reg [width-1:0]     odata_i;

   reg [width-1:0]  odata;
   reg [width-1:0]  odata_mem;
   reg [width-1:0]  data [0:depth-1];
   reg [width-1:0]  idata_d1;
   wire [width-1:0] idata_dd;
   reg              collision_d1; 
   wire             collision, collision_dd;

   generate
      if (input_flops > 0) begin
         verilog_memory_pipe_fpga #(.w(1),       .d(input_flops))  flopre(.i(renable), .o(renable_i), .clk(clk));
         verilog_memory_pipe_fpga #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(clk));
         verilog_memory_pipe_fpga #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(clk));
         verilog_memory_pipe_fpga #(.w(depth_w), .d(input_flops))  flopra(.i(raddr),   .o(raddr_i),   .clk(clk));
         verilog_memory_pipe_fpga #(.w(depth_w), .d(input_flops))  flopwa(.i(waddr),   .o(waddr_i),   .clk(clk));
      end else begin
         assign renable_i = renable;
         assign wenable_i = wenable;
         assign idata_i   = idata;
         assign raddr_i   = raddr;
         assign waddr_i   = waddr;
      end
      if (output_flops > 0) begin
         verilog_memory_pipe_fpga #(.w(width), .d(output_flops)) flopod(.i(odata_mem),    .o(odata_i),      .clk(clk));
      end else begin
         assign odata_i = odata_mem;
      end
      if (output_flops > 0) begin
         if (write_through == 1) begin
            verilog_memory_pipe_fpga #(.w(1),     .d(output_flops)) flopoc(.i(collision_d1), .o(collision_dd), .clk(clk));
            verilog_memory_pipe_fpga #(.w(width),     .d(output_flops)) flopoi(.i(idata_d1),     .o(idata_dd),     .clk(clk));
         end
      end else begin
         if (write_through == 1) begin
            assign collision_dd = collision_d1;
            assign idata_dd     = idata_d1;
         end
      end
   endgenerate

   integer i;
   generate
      if (pre_load) begin
         initial begin: DRESET
            for (i=0; i<depth; i=i+1) begin
               data[i] = reset_value;
            end
         end
      end         
   endgenerate
   
   generate
      if(mask_w > 1) begin: WMASK
         wire [mask_w-1:0] wmask_i;
         if (input_flops > 0) begin
            verilog_memory_pipe_fpga #(.w(mask_w), .d(input_flops))  flopwm(
                .i(wmask), .o(wmask_i), .clk(clk)
            );
         end else begin
            assign wmask_i = wmask;
         end
         always @(posedge clk) begin
            `ifndef SYNTHESIS
            odata_mem <= 'x;
            `endif
            if (renable_i == 1) begin
               odata_mem <= data[raddr_i];
            end
            if (wenable_i == 1) begin
               for (i=0; i < mask_w; i = i + 1) begin
                  if (wmask_i[i]) begin
                     data[waddr_i][i * wgran +: wgran] <= idata_i[i * wgran +: wgran];
                  end
               end
            end
         end
      end else begin: NOWMASK
         always @(posedge clk) begin
            `ifndef SYNTHESIS
            odata_mem <= 'x;
            `endif
            if (renable_i == 1) begin
               odata_mem <= data[raddr_i];
            end
            if (wenable_i == 1) begin
               data[waddr_i] <= idata_i;
            end
         end
      end
   endgenerate
   
   generate
      if (write_through==0) begin
	 always @(*) begin
            odata = odata_i;
         end
      end else begin
	 assign collision = ((wenable_i==1) && (renable_i==1) && raddr_i==waddr_i);
         initial collision_d1 = 0;
         initial idata_d1 = 0;
	 always @(posedge clk) begin
            begin
	       collision_d1 <= collision;
	       idata_d1     <= idata_i;
	    end
	 end
	 always @(*) begin
	    if (collision_dd==0) begin
	       odata = odata_i;               
	    end else begin
	       odata = idata_dd;
	    end
	 end
      end // else: !if(write_through==0)
   endgenerate
endmodule
