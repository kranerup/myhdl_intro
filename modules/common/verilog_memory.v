`timescale 1ns/10ps

`ifndef membus_out_width
  `define membus_out_width 2
  `define membus_in_width 2
`endif

module verilog_memory_ff(i, o, clk, rstn);
   parameter w = 1;
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;
   input          rstn;

   reg    [w-1:0] o;

   always @(posedge clk, negedge rstn) begin
      if (rstn==0) begin
         o <= 0;
      end else begin
         o <= i;
      end
   end
endmodule

module verilog_memory_pipe(i,o,clk,rstn);
   parameter w = 1;
   parameter d = 1; // Only 0 and 1 supported, for now.
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;
   input          rstn;

   generate
      if (d == 0) begin
         assign o = i;
      end else begin
         verilog_memory_ff #(.w(w) ) flop(i, o, clk, rstn);
      end
   endgenerate

endmodule // pipe

module verilog_memory(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
                      wmask,
		      renable,
		      clk,
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
   input [`membus_in_width-1:0] dft_in;
   output [`membus_out_width-1:0] dft_out;

   wire [width-1:0]    idata_i;
   wire [depth_w-1:0]  raddr_i;
   wire [depth_w-1:0]  waddr_i;
   wire                wenable_i;
   wire                renable_i;

   reg [width-1:0]     odata_i;

   wire [width-1:0] odata;
   reg [width-1:0]  odata_mem;
   reg [width-1:0]  data [0:depth-1];
   reg [width-1:0]  idata_d1;
   reg 		    collision, collision_d1;

   assign dft_out = {`membus_out_width{|dft_in}};

   generate
      if (input_flops > 0) begin
         verilog_memory_pipe #(.w(1),       .d(input_flops))  flopre(.i(renable), .o(renable_i), .clk(clk), .rstn(rstn));
         verilog_memory_pipe #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(clk), .rstn(rstn));
         verilog_memory_pipe #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(clk), .rstn(rstn));
         verilog_memory_pipe #(.w(depth_w), .d(input_flops))  flopra(.i(raddr),   .o(raddr_i),   .clk(clk), .rstn(rstn));
         verilog_memory_pipe #(.w(depth_w), .d(input_flops))  flopwa(.i(waddr),   .o(waddr_i),   .clk(clk), .rstn(rstn));
      end else begin
         assign renable_i = renable;
         assign wenable_i = wenable;
         assign idata_i   = idata;
         assign raddr_i   = raddr;
         assign waddr_i   = waddr;
      end
      if (output_flops > 0) begin
         verilog_memory_pipe #(.w(width),   .d(output_flops)) flopod(.i(odata_i), .o(odata),     .clk(clk), .rstn(rstn));
      end else begin
         assign odata = odata_i;
      end
   endgenerate

   integer i;

   generate
      if(mask_w > 1) begin: WMASK
         wire [mask_w-1:0] wmask_i;
         if (input_flops > 0) begin
            verilog_memory_pipe #(.w(mask_w), .d(input_flops))  flopwm(
                .i(wmask), .o(wmask_i), .clk(clk), .rstn(rstn)
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
      if ((pre_load==1) && (reset_value>=0)) begin
	 integer i;
	 initial begin
	    for (i=0; i<depth; i=i+1) begin
               data[i] = reset_value;
	    end
	 end
      end else begin
      end
   endgenerate

   generate
      if (write_through==0) begin
	 always @(*) begin
	    odata_i = odata_mem;
	 end
      end else begin
	 always @(*) begin
	    collision = 0;
	    if ((wenable_i==1) && (renable_i==1) && raddr_i==waddr_i) begin
	       collision = 1;
	    end
	 end
	 always @(posedge clk, negedge rstn) begin
	    if (rstn==0) begin
	       collision_d1 <= 0;
	       idata_d1     <= 0;
	    end else begin
	       collision_d1 <= collision;
	       idata_d1     <= idata_i;
	    end
	 end
	 always @(*) begin
	    if (collision_d1==0) begin
	       odata_i = odata_mem;
	    end else begin
	       odata_i = idata_d1;
	    end
	 end
      end // else: !if(write_through==0)
   endgenerate
endmodule
