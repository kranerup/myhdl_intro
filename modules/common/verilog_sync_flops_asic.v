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

  always_comb
    outp = sync_ff[ depth-1 ];

endmodule
