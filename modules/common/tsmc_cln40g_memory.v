`timescale 1ns/10ps

module REPLACE_WNAME(
		      idata,
		      odata,
		      waddr,
		      raddr,
		      wenable,
		      renable,
		      clk,
		      rstn
		      );
   
   parameter width = 1;
   parameter depth = 1;
   parameter depth_w = 1;
   parameter write_through = 0;

   parameter mw = 1;
   parameter md = 1;
   parameter md_w = 1;
   parameter cols = 1; // number of memories wide
   parameter rows = 1; // number of memories tall
   parameter rf   = 0; // Select between Register file and SRAM compiler
   parameter input_flops = 0;
   parameter output_flops = 0;
   
   input [width-1:0]   idata;
   output [width-1:0]  odata;
   input [depth_w-1:0] waddr;
   input [depth_w-1:0] raddr;
   input 	       wenable;
   input 	       renable;
   input 	       clk;
   input 	       rstn;

   reg [width-1:0]     odata;
   
   reg [width-1:0]   idata_ff;
   reg [width-1:0]   odata_x;
   reg [depth_w-1:0] waddr_ff;
   reg [depth_w-1:0] raddr_ff;
   reg 	             wenable_ff;
   reg 	             renable_ff;

   generate
      if (input_flops==1) begin : inflops
         always@(posedge clk, negedge rstn) begin
            if (rstn==0) begin
               idata_ff   <= 0;
               waddr_ff   <= 0;
               raddr_ff   <= 0;
               wenable_ff <= 0;
               renable_ff <= 0;
            end else begin
               idata_ff   <= idata;
               waddr_ff   <= waddr;
               raddr_ff   <= raddr;
               wenable_ff <= wenable;
               renable_ff <= renable;
            end // else: !if(rstn==0)
         end // always@ (posedge clk, negedge rstn)
      end else begin // block: inflops
         always_comb begin
            idata_ff   = idata;
            waddr_ff   = waddr;
            raddr_ff   = raddr;
            wenable_ff = wenable;
            renable_ff = renable;
         end
      end // else: !if(input_flops==1)
      if (output_flops==1) begin : outflops
         always@(posedge clk, negedge rstn) begin
            if (rstn==0) begin
               odata    <= 0;
            end else begin
               odata    <= odata_x;
            end // else: !if(rstn==0)
         end // always@ (posedge clk, negedge rstn)
      end else begin // block: inflops
         always_comb begin
            odata    = odata_x;
         end
      end // else: !if(output_flops==1)
   endgenerate
   
   
   wire [(mw*cols)-1:0] mem_odata, mem_idata;
   assign mem_idata = idata_ff;

   wire [md_w-1:0]     AA, AB;
   assign AA = raddr_ff;
   assign AB = waddr_ff;
   wire 	       mem_collision;

   wire 	       mem_renable;
   assign mem_renable = renable_ff && !mem_collision;

   generate
      if (write_through==1) begin : genblk1
	 reg collision;
	 reg collision_d1;
	 reg [width-1:0] idata_d1;
	 always@(posedge clk, negedge rstn) begin
	    if (rstn==0) begin
	       idata_d1 <= 0;
	       collision_d1 <= 0;
	    end else begin  
	       idata_d1 <= idata_ff;
	       collision_d1 <= collision;
	    end
	 end
	 always_comb begin
	    if (wenable_ff==1 && renable_ff==1 && waddr_ff==raddr_ff) begin
	       collision = 1;
	    end else begin
	       collision = 0;
	    end
	 end
	 assign odata_x = collision_d1 ? idata_d1 : mem_odata;
	 assign mem_collision = collision;
      end else begin : genblk2 // if (write_through==1)
	 assign odata_x = mem_odata;
	 assign mem_collision = 0;
      end // else: !if(write_through==1)
      if (rf==0) begin  : genblk3
	 genvar CCNT;
	 for (CCNT=0; CCNT<cols; CCNT=CCNT+1) begin : X
	       REPLACE_MNAME mem (
				  // Port A (read)
				  .CLKA(clk),
				  .CENA(~mem_renable),
				  .WENA(1'b1),
				  .AA(AA),
				  .DA({mw{1'b0}}), 
				  .QA(mem_odata[(mw*(CCNT+1))-1:mw*CCNT]),
				  // Port B (write)
				  .CLKB(clk),
				  .CENB(~wenable_ff),
				  .WENB(~wenable_ff),
				  .AB(AB),
				  .DB(mem_idata[(mw*(CCNT+1))-1:mw*CCNT]),
				  // Settings
				  .EMAA(3'b0), .EMAWA(2'b0), .EMASA(1'b0),					    
				  .EMAB(3'b0), .EMAWB(2'b0), .EMASB(1'b0), 
				  .TENA(1'b1), .TCENA(1'b1), .TWENA(1'b1), .TAA({md_w{1'b0}}), .TDA({mw{1'b0}}), .TQA({mw{1'b0}}), 
				  .TENB(1'b1), .TCENB(1'b1), .TWENB(1'b1), .TAB({md_w{1'b0}}), .TDB({mw{1'b0}}), .TQB({mw{1'b0}}), 
				  .BENA(1'b1),  .BENB(1'b1), 
				  .RET1N(1'b1), 
				  .STOVA(1'b0), .STOVB(1'b0), 
				  .COLLDISN(1'b1)					    
				  );
	 end // block: X
      end else begin // if (rf==0)
	 genvar CCNT;
	 for (CCNT=0; CCNT<cols; CCNT=CCNT+1) begin : X
	       REPLACE_MNAME mem (
				  // Port A (read)
				  .CLKA(clk),
				  .CENA(~mem_renable),
				  .AA(AA),
				  .QA(mem_odata[(mw*(CCNT+1))-1:mw*CCNT]),
				  // Port B (write)
				  .CLKB(clk),
				  .CENB(~wenable_ff),
				  .AB(AB),
				  .DB(mem_idata[(mw*(CCNT+1))-1:mw*CCNT]),
				  // Settings
				  .EMAA(3'b0), .EMASA(1'b0),					    
				  .EMAB(3'b0), .EMAWB(2'b0), 
				  .TENA(1'b1), .TCENA(1'b1), .TAA({md_w{1'b0}}), .TQA({mw{1'b0}}), 
				  .TENB(1'b1), .TCENB(1'b1), .TAB({md_w{1'b0}}), .TDB({mw{1'b0}}), 
				  .BENA(1'b1), 
				  .RET1N(1'b1), 
				  .STOVA(1'b0), .STOVB(1'b0), 
				  .COLLDISN(1'b1)					    
				  );
	 end // block: X
      end // else: !if(rf==0)
   endgenerate
   
   ///////////////////////////////////////
   // Dual port SRAM
   ///////////////////////////////////////
   // Data mux outputs:             CENYA, WENYA, AYA, DYA, CENYB, WENYB, AYB, DYB, 
   // Data out:                     QA, QB,
   // Port A inputs:                CLKA, CENA, WENA, AA, DA, 
   // Port B inputs:                CLKB, CENB, WENB, AB, DB, 
   // Margin adjustment             port A: EMAA, EMAWA, EMASA, 
   // Margin adjustment             port B: EMAB, EMAWB, EMASB, 
   // Test port A:                  TENA, TCENA, TWENA, TAA, TDA, TQA, 
   // Test port B:                  TENB, TCENB, TWENB, TAB, TDB, TQB, 
   // Bypass enable:                BENA,  BENB, 
   // Retention enable:             RET1N, 
   // Self timing override:         STOVA, STOVB, 
   // Disable collisinon detection: COLLDISN
endmodule   
