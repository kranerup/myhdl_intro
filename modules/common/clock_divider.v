module clock_divider (
                        master_clk,     
                        clk
                        );
   parameter divisor = 1;
   input               master_clk;     
   output              clk;    

   logic                     mask;
   logic [$clog2(divisor):0] cnt;

   generate
      if (divisor==1) begin
         assign mask = 1;
      end else begin
         initial
           cnt = divisor-1;
         
         always@(negedge master_clk)
           if (cnt==divisor-1)
             cnt <= 0;         
           else
             cnt <= cnt + 1;

         always@(negedge master_clk)
           if (cnt==0)
             mask <= 1;         
           else
             mask <= 0;
      end // else: !if(divisor==1)
   endgenerate
   assign clk = master_clk & mask;

endmodule
