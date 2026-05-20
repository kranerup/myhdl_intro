`timescale 1ns/10ps

module verilog_sync_flops( inp, outp, clk, rstn );
  parameter width = 1;
  parameter depth = 1;

  input  [width-1:0]  inp;
  output [width-1:0]  outp;
  reg    [width-1:0]  outp;
  input               clk;
  input               rstn;

  (* ASYNC_REG = "TRUE" *) reg [width-1:0]     sync_ff [depth-1:0];

  `ifdef FPGA_TECH
    // In FPGA the reset is not used, instead initial block
    // resets the flops.
    initial begin
      integer i;
      for (i=0; i<depth; i++) begin
         sync_ff[i] <= 0;
      end
    end

    always @(posedge clk)  begin
      integer i;
      for (i=0; i<depth; i++) begin
        if ( i == 0 )
          sync_ff[0] <= inp;
        else
          sync_ff[i] <= sync_ff[ i-1 ];
      end
    end

  `else
    // In ASIC technology reset is used to initalize flops.
    always @(posedge clk)  begin
      integer i;
      for (i=0; i<depth; i++) begin
        if ( rstn == 0 )
          sync_ff[i] <= 0;
        else begin
          if ( i == 0 )
            sync_ff[0] <= inp;
          else
            sync_ff[i] <= sync_ff[ i-1 ];
        end
      end
    end
  `endif

  always_comb
    outp = sync_ff[ depth-1 ];

endmodule
