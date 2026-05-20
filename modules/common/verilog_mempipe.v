
`ifndef membus_out_width
  `define membus_out_width 2
  `define membus_in_width 2
`endif

module verilog_mempipe (
                        idata,     
                        odata,    
                        enable,
                        clk,    
                        rstn,   
                        dft_in, 
                        dft_out
                        );
   parameter width = 1;
   parameter depth = 1;
   parameter input_flops  = 0;
   parameter output_flops = 0;
   parameter depth_w      = $clog2(depth-input_flops-output_flops-1);
   input [width-1:0]              idata;     
   output [width-1:0]             odata;    
   input                          enable;
   input                          clk;    
   input                          rstn;   
   input [`membus_in_width-1:0]   dft_in; 
   output [`membus_out_width-1:0] dft_out;
   
   wire [width-1:0]                                mdata;
   reg [depth_w-1:0]                               waddr;
   reg [depth_w-1:0]                               raddr;
   reg                                             renable;
   reg                                             wenable;
   
   always @ (posedge clk, negedge rstn) begin : pipelogic
      integer i;
      if (rstn==0) begin
         renable <= 0;
         wenable <= 0;
         raddr   <= 0;
         waddr   <= depth-1-input_flops-output_flops;
      end else if (enable==1) begin
         raddr <= raddr+1;
         renable <= 1;
         wenable <= 1;
         waddr <= raddr;
         if (raddr==depth-1-input_flops-output_flops) begin
            raddr   <= 0;
         end
      end else begin
         renable <= 0;
         wenable <= 0;
      end
   end
   assign odata = mdata;

   verilog_memory 
     #(
       .width(width), 
       .depth(depth-input_flops-output_flops), 
       .depth_w(depth_w), 
       .input_flops(input_flops), 
       .output_flops(output_flops) ) 
   meminst( idata, mdata, waddr, raddr, wenable, renable, clk, rstn, dft_in, dft_out);

endmodule   
