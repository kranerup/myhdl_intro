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
// verilog_memory_xilinx_ecc instanciates block ram (or ultra ram)
// with ECC. The data width is rounded up to n*64, so it may be quite expensive
// for narrow RAMs. This rounding is required by Vivado.
//
// This module handles the collisions, and instanciates xilinx_ecc_block_memory:
// xilinx_ecc_block_memory, in turn rounds up the data-bus, and instanciates xilinx_xpm_memory_sdpram
// which fiddles with all the knobs on the vivado macro to make an ECC memory bank.
//

// xpm_memory_sdpram: Simple Dual Port RAM
// Xilinx Parameterized Macro, version 2021.2

module xilinx_xpm_memory_sdpram(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
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
   parameter output_flops = 0;
   parameter ecc = 0;
   parameter reset_value = 0;
   parameter dual_clock = 0;   
   
   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input 	       renable;
   input 	       rclk;
   input 	       wclk;
   input 	       rstn;
   input [`membus_in_width-1:0] dft_in;
   output [`membus_out_width-1:0] dft_out;
   
   reg [width-1:0]  odata;
   
   wire dbiterrb;
   assign dft_out[0] = dbiterrb; 
   wire sbiterrb;
   assign dft_out[1] = sbiterrb;
   wire injectdbiterra;
   assign injectdbiterra = dft_in[0];
   wire injectsbiterra;
   assign injectsbiterra = dft_in[1];
   reg  regceb = 1'b1;
   reg  sleep = 1'b0;
   reg  wea = 1'b1;
   
   `pktarc_xpm_memory_sdpram #(
                               .ADDR_WIDTH_A(depth_w),         // DECIMAL
                               .ADDR_WIDTH_B(depth_w),         // DECIMAL
                               .AUTO_SLEEP_TIME(0),            // DECIMAL
                               .BYTE_WRITE_WIDTH_A(width),     // DECIMAL
                               .CASCADE_HEIGHT(0),             // DECIMAL
                               .CLOCKING_MODE(dual_clock ? "independent_clock" : "common_clock"), // String
                               .ECC_MODE(ecc ? "both_encode_and_decode" : "no_ecc"),            // String
                               .MEMORY_INIT_FILE("none"),      // String
                               .MEMORY_INIT_PARAM("0"),        // String
                               .MEMORY_OPTIMIZATION("true"),   // String
                               .MEMORY_PRIMITIVE("block"),      // String
                               .MEMORY_SIZE(depth*width),      // DECIMAL
                               .MESSAGE_CONTROL(0),            // DECIMAL
                               .READ_DATA_WIDTH_B(width),      // DECIMAL
                               .READ_LATENCY_B(output_flops+1), // DECIMAL
                               .READ_RESET_VALUE_B("0"),       // String
                               .RST_MODE_A("SYNC"),            // String
                               .RST_MODE_B("SYNC"),            // String
                               .SIM_ASSERT_CHK(0),             // DECIMAL; 0=disable simulation messages, 1=enable simulation messages
                               .USE_EMBEDDED_CONSTRAINT(0),    // DECIMAL
                               .USE_MEM_INIT(0),               // DECIMAL
                               .USE_MEM_INIT_MMI(0),           // DECIMAL
                               .WAKEUP_TIME("disable_sleep"),  // String
                               .WRITE_DATA_WIDTH_A(width),     // DECIMAL
                               .WRITE_MODE_B("read_first"),   // String
                               .WRITE_PROTECT(1)               // DECIMAL
                               )
   xpm_memory_sdpram_inst (
                           .dbiterrb(dbiterrb),             // 1-bit output: Status signal to indicate double bit error occurrence
                           // on the data output of port B.
                           
                           .doutb(odata),                   // READ_DATA_WIDTH_B-bit output: Data output for port B read operations.
                           .sbiterrb(sbiterrb),             // 1-bit output: Status signal to indicate single bit error occurrence
                           // on the data output of port B.
                           
                           .addra(waddr),                   // ADDR_WIDTH_A-bit input: Address for port A write operations.
                           .addrb(raddr),                   // ADDR_WIDTH_B-bit input: Address for port B read operations.
                           .clka(dual_clock ? wclk : rclk),                     // 1-bit input: Clock signal for port A. Also clocks port B when
                           // parameter CLOCKING_MODE is "common_clock".
                           
                           .clkb(rclk),                     // 1-bit input: Clock signal for port B when parameter CLOCKING_MODE is
                           // "independent_clock". Unused when parameter CLOCKING_MODE is
                           // "common_clock".
                           
                           .dina(idata),                     // WRITE_DATA_WIDTH_A-bit input: Data input for port A write operations.
                           .ena(wenable),                       // 1-bit input: Memory enable signal for port A. Must be high on clock
                           // cycles when write operations are initiated. Pipelined internally.
                           
                           .enb(renable),                       // 1-bit input: Memory enable signal for port B. Must be high on clock
                           // cycles when read operations are initiated. Pipelined internally.
                           
                           .injectdbiterra(injectdbiterra), // 1-bit input: Controls double bit error injection on input data when
                           // ECC enabled (Error injection capability is not available in
                           // "decode_only" mode).
                           
                           .injectsbiterra(injectsbiterra), // 1-bit input: Controls single bit error injection on input data when
                           // ECC enabled (Error injection capability is not available in
                           // "decode_only" mode).
                           
                           .regceb(regceb),                 // 1-bit input: Clock Enable for the last register stage on the output
                           // data path.
                           
                           .rstb(ecc ? 1'b0 : ~rstn),       // 1-bit input: Reset signal for the final port B output register stage.
                           // Synchronously resets output port doutb to the value specified by
                           // parameter READ_RESET_VALUE_B.
                           
                           .sleep(sleep),                   // 1-bit input: sleep signal to enable the dynamic power saving feature.
                           .wea(wea)                        // WRITE_DATA_WIDTH_A/BYTE_WRITE_WIDTH_A-bit input: Write enable vector
                           // for port A input data port dina. 1 bit wide when word-wide writes are
                           // used. In byte-wide write configurations, each bit controls the
                           // writing one byte of dina to address addra. For example, to
                           // synchronously write only bits [15-8] of dina when WRITE_DATA_WIDTH_A
                           // is 32, wea would be 4'b0010.                           
                           );
   
endmodule // xilinx_xpm_memory_sdpram

// End of xpm_memory_sdpram_inst instantiation


// This module will just set the ecc param and pad the data so that it is a multiple of 64 (required by vivado for ecc)
module xilinx_ecc_block_memory(
	   idata,
	   odata,
	   waddr,
	   raddr,
	   wenable,
	   renable,
	   rclk,
           wclk,
	   rstn,
           dft_in,
           dft_out
	   );
   parameter width = 1024;
   parameter depth = 3072;
   parameter depth_w = 12;
   parameter output_flops = 0;
   parameter reset_value = 0;   // Note that XPM memories with ECC do not support reset_values other than 0
   parameter dual_clock = 0;   
     
   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input 	       renable;
   input 	       rclk;
   input 	       wclk;
   input 	       rstn;
   input [`membus_in_width-1:0] dft_in;
   output [`membus_out_width-1:0] dft_out;

   localparam chunk = 64;
   
   localparam wc = width/chunk;
   localparam cwidth = wc*chunk < width ? (wc+1)*chunk : wc*chunk;
   
   wire [cwidth-1:0] cidata;
   wire [cwidth-1:0] codata;
   assign cidata = idata;
   assign odata = codata;   
   
   xilinx_xpm_memory_sdpram #(
                              .width(cwidth),
                              .depth(depth),
                              .depth_w(depth_w),
                              .output_flops(output_flops),
                              .ecc(1),
                              .reset_value(reset_value),
                              .dual_clock(dual_clock)
                              )
   blockmem(
           .idata(cidata),
           .odata(codata),
           .waddr(waddr),
           .raddr(raddr),
           .wenable(wenable),
           .renable(renable),
           .rclk(rclk),
           .wclk(wclk),
           .rstn(rstn),
           .dft_in(dft_in),
           .dft_out(dft_out)
           );
endmodule // xilinx_ecc_block_memory

module verilog_memory_ff_xilinx_ecc(i, o, clk);
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

module verilog_memory_pipe_xilinx_ecc(i,o,clk);
   parameter w = 1;
   parameter d = 1; // Only 0 and 1 supported, for now.
   input  [w-1:0] i;
   output [w-1:0] o;
   input          clk;

   generate
      if (d == 0) begin
         assign o = i;
      end else begin
         verilog_memory_ff_xilinx_ecc #(.w(w) ) flop(i, o, clk);
      end
   endgenerate

endmodule // pipe


module verilog_memory_xilinx_ecc(
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
   input 	       clk;
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
         verilog_memory_pipe_xilinx_ecc #(.w(1),       .d(input_flops))  flopre(.i(renable), .o(renable_i), .clk(clk));
         verilog_memory_pipe_xilinx_ecc #(.w(1),       .d(input_flops))  flopwe(.i(wenable), .o(wenable_i), .clk(clk));
         verilog_memory_pipe_xilinx_ecc #(.w(width),   .d(input_flops))  flopid(.i(idata),   .o(idata_i),   .clk(clk));
         verilog_memory_pipe_xilinx_ecc #(.w(depth_w), .d(input_flops))  flopra(.i(raddr),   .o(raddr_i),   .clk(clk));
         verilog_memory_pipe_xilinx_ecc #(.w(depth_w), .d(input_flops))  flopwa(.i(waddr),   .o(waddr_i),   .clk(clk));
      end else begin
         assign renable_i = renable;
         assign wenable_i = wenable;
         assign idata_i   = idata;
         assign raddr_i   = raddr;
         assign waddr_i   = waddr;
      end
      if (output_flops > 0) begin
         if (write_through == 1) begin
            verilog_memory_pipe_xilinx_ecc #(.w(1),     .d(output_flops)) flopoc(.i(collision_d1), .o(collision_dd), .clk(clk));
            verilog_memory_pipe_xilinx_ecc #(.w(width),     .d(output_flops)) flopoi(.i(idata_d1),     .o(idata_dd),     .clk(clk));
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
      if (write_through==0) begin
	 always @(*) begin
            odata = odata_i;
         end
      end else begin
	 always @(*) begin
	    collision = 0;
	    if ((wenable_i==1) && (renable_i==1) && raddr_i==waddr_i) begin
	       collision = 1;
	    end
	 end
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

   xilinx_ecc_block_memory #(
                             .width(width),
                             .depth(depth),
                             .depth_w(depth_w),
                             .output_flops(output_flops),
                             .reset_value(reset_value),
                             .dual_clock(1'b0)
                             )
   eccmeminst(
              .idata(idata_i),
              .odata(odata_i),
              .waddr(waddr_i),
              .raddr(raddr_i),
              .wenable(wenable_i),
              .renable(renable_i),
              .rclk(clk),
              .wclk(clk),
              .rstn(rstn),
              .dft_in(dft_in),
              .dft_out(dft_out)                 
              );
   
   
endmodule
