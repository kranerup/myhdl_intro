// -----------------------------------------------------------------------
// This file contains the RTL and behavioral code needed to instantiate
// the Cavium TCAM. The top module to instantiate is named "cam_ternary".
// The module code here is slightly modified from what is delivered
// from Cavium to allow working without defines and to allow generic
// instantiation.
//
// -----------------------------------------------------------------------

// ************************************************************************
// *                                                                      *
// *  CAVIUM CONFIDENTIAL AND PROPRIETARY NOTE                            *
// *                                                                      *
// *  This software contains information confidential and proprietary     *
// *  to Cavium, Inc. It shall not be reproduced in whole or in part,     *
// *  or transferred to other documents, or disclosed to third parties,   *
// *  or used for any purpose other than that for which it was obtained,  *
// *  without the prior written consent of Cavium, Inc.                   *
// *                                                                      *
// *  Copyright 2017, Cavium, Inc.  All rights reserved.                  *
// *                                                                      *
// ************************************************************************
// * Author      : Rahul Mehrotra
// * Description : Ternary CAM model
//                 Basic ternary CAM model
//                 Supports global bit wise masking
//                 Valid bit with ability to invalidate the whole cam at once
// ************************************************************************
//
//=============================================================================
//                 OPs Description
//
//  CAM: Evaluate happens in 1A, captured by latch,
//       output is hit_1a signals arriving late in 1A cycle to the outside
//       flop. Multihit is possible.
//
//       Control signals: ccmd_0a + cdat_0a + cmsk_0a
//                OUTPUT: cam_hitvec_1a
//  WRITE:
//       Decode will happen in 1A, write evaluate will happen in 1B. Write
//       will be finished by start of 2A cycle.
//
//       Control signals: wcmd_0a + wdat*_0a + rwdix_0a
//                OUTPUT: NONE
//  INVAL:
//       Invals will be finished by start of 2A cycle
//
//       Control signals: icmd_0a
//                OUTPUT: NONE
//  READ:
//       Decodde and bitline precharge will happen in 1A.
//       Read eval will happen in 1B.
//       Sense amp fires in 2A, so output is ready early in 2A cycle.
//
//       Control signals: rcmd_0a + rwidx_0a
//                OUTPUT: rdat*_2a
//=============================================================================
//
//  In the same cycle we CAN CAM and READ.
//  Write is explicit OP so NO (CAM & WR) and NO (RD & WR)
//  Inval is also explicit OP so NO (INVAL & CAM) ,NO (INVAL & WR) and NO (INVAL & RD)
//=============================================================================
// Clock enable - Has to be on one cycle before any command.
//=============================================================================

//`include "cn_defines.vh"
module cam_ternary_beh
  #(parameter NENT=64, //Number of Entries
    parameter WIDTH=32,   //Cam width including the valid bit
    parameter NENT_LOG2 = $clog2(NENT)
    )
  (
   // ----------------------------------------------------------------------
   // Misc clocking and control signals
   // ----------------------------------------------------------------------
   //fixme drive clk_en.
   //input 		      clk_en, //cn_lint_off_line CN_UNUSED_IN //Coarse clock enable // Should be risen at least one cycle before any cmd is issued
   input 			sclk,

   input 			scan_mode, //cn_lint_off_line CN_UNUSED_IN
   input 			se_in, //cn_lint_off_line CN_UNUSED_IN
   input 			scan_in_sclk, //cn_lint_off_line CN_UNUSED_IN
   output logic 		scan_out_sclk,//cn_lint_off_line CN_UNUSED_OUT

   // ----------------------------------------------------------------------
   // CAM Lookup Interface
   // ----------------------------------------------------------------------

   input 			ccmd_0a, //Cam cmd
   input 			icmd_0a, //Inval cmd. Use this to inval the whole cam at once
   input [WIDTH-2:0] 		cdat_0a, //Looked up key
   input [WIDTH-2:0] 		cmsk_0a, //Mask assosiated with the key
   output logic [NENT-1:0] 	hitvec_1a, //raw hit outputs
   output logic [NENT_LOG2-1:0] hitidx_1a, //encoded hit
   output logic 		hit_1a, //if cam hits
   output logic 		multihit_1a, // if cam has multihits. index will be garbage then

   // ----------------------------------------------------------------------
   // RD/WR interface
   // ----------------------------------------------------------------------
   //
   input 			rcmd_0a, //rd cmd
   input 			wcmd_0a, //wr cmd
   input [WIDTH-2:0] 		wdat_0a,
   input [WIDTH-2:0] 		wmsk_0a,
   input 			wdat_val_0a, //valid bit
   input [NENT_LOG2-1:0] 	rwidx_0a, //rd/wr index
   output logic [WIDTH-2:0] 	rdat_2a,
   output logic [WIDTH-2:0] 	rdat0_2a, //read of cell 0 of tcam cell {~dat & ~mask} //Encoded read data needed for Bug# 31206
   output logic [WIDTH-2:0] 	rmsk_2a,
   output logic 		rdat_val_2a //read valid bit

   );


  // flop inputs
  logic [WIDTH-2:0] 	      rdat1_2a; //read of cell 1 of tcam cell { dat & ~mask}
  logic 		      ccmd_1a;
  logic 		      icmd_1a;
  logic 		      rcmd_1a;
  logic 		      wcmd_1a;
  logic [NENT_LOG2-1:0]       rwidx_1a;
  logic [WIDTH-2:0] 	      cdat_1a;
  logic [WIDTH-2:0] 	      cmsk_1a;
  logic [WIDTH-2:0] 	      wdat0_1a;
  logic [WIDTH-2:0] 	      wdat1_1a;
  logic 		      wdat_val_1a;

  logic [(WIDTH-2):0] 	      wdat0_0a ;
  logic [(WIDTH-2):0] 	      wdat1_0a ;

  always_comb begin
    //Write data encode

    // TCAM CELL
    // wdat is written in encoded format
    // CELL 1 -->  dat & ~mask
    // CELL 0 --> ~dat & ~mask
    // ----------------------------
    // |            |             |
    // |            |             |
    // |  CELL 1    |   CELL 0    |
    // |            |             |
    // |dat & ~mask |~dat & ~mask |
    // ----------------------------

    wdat0_0a = ~wdat_0a & ~wmsk_0a;
    wdat1_0a =  wdat_0a & ~wmsk_0a;

    //Read data decode
    //When mask is 1, rdat dat will be 0 as it can't be recovered back
    //Because both cells Cell1/Cell0 of the tcam will be written as 0 0.
    rdat_2a = rdat1_2a;
    rmsk_2a = ~(rdat0_2a | rdat1_2a);
  end

  always_ff @(posedge sclk) begin
    ccmd_1a 	  <= ccmd_0a;
    icmd_1a 	  <= icmd_0a;
    rcmd_1a 	  <= rcmd_0a;
    wcmd_1a 	  <= wcmd_0a;

    cdat_1a       <= cdat_0a;
    cmsk_1a       <= cmsk_0a;
    rwidx_1a      <= rwidx_0a;
    wdat0_1a      <= wdat0_0a;
    wdat1_1a      <= wdat1_0a;
    wdat_val_1a   <= wdat_val_0a;

    XCHK_CCMD: assert(~$isunknown(ccmd_1a)) else $display("Cam command ccmd_1a is X");
    RW_COLL : assert($onehot0({wcmd_1a, rcmd_1a})) else $display("Illegal command combination - WR & RD");
    CW_COLL : assert($onehot0({ccmd_1a, wcmd_1a})) else $display("Illegal command combination - CAM & WR");
    IW_COLL : assert($onehot0({icmd_1a, wcmd_1a})) else $display("Illegal command combination - INVAL & WR");
    IR_COLL : assert($onehot0({icmd_1a, rcmd_1a})) else $display("Illegal command combination - INVAL & RD");
    IC_COLL : assert($onehot0({icmd_1a, ccmd_1a})) else $display("Illegal command combination - INVAL & CAM");
  end

  typedef struct packed {
    logic [WIDTH-2:0] dat0;
    logic [WIDTH-2:0] dat1;
    logic 	      valid;
  } dat_t;


`ifdef SHERLOCK
  dat_t dat[NENT-1:0];
`else
  dat_t[NENT-1:0] dat;
`endif

  // CAM during 1a
  always_latch begin
    if (ccmd_1a & sclk) begin	// cn_lint_off_line CN_LATCH
      for (int i = 0; i < NENT; i = i + 1) begin
	hitvec_1a[i] =  (dat[i].valid & ~|((dat[i].dat1 ^ (cdat_1a & (dat[i].dat1 | dat[i].dat0))) & ~cmsk_1a)); // cn_lint_off_line CN_LATCH
      end
    end
  end
  encoder_m #(
	      .N(NENT)
	      ) enc(
		    // Outputs
		    .hit			(hit_1a),
		    .multihit		        (multihit_1a),
		    .index			(hitidx_1a[NENT_LOG2-1:0]),
		    // Inputs
		    .match			(hitvec_1a[NENT-1:0]));

  // writes/inval during 1b
  always_ff @(negedge sclk) begin
    if (wcmd_1a) begin
      dat[rwidx_1a] <= '{valid:wdat_val_1a, dat0:wdat0_1a, dat1:wdat1_1a};
      XCHK_RWIDX_W: assert(~$isunknown(rwidx_1a)) else $display("RWIDX_W rwidx_1a is X");
    end
    XCHK_WCMD: assert(~$isunknown(wcmd_1a)) else $display("Write commmand wcmd_1a is X");

    if (icmd_1a) begin
      for (int i = 0; i < NENT; i = i + 1) begin
	dat[i] <= '{valid:'0, dat0:dat[i].dat0, dat1:dat[i].dat1};
      end
    end
    XCHK_ICMD: assert(~$isunknown(icmd_1a)) else $display("Inval commmand icmd_1a is X");
  end


  // reads during 2a
  always_ff @(posedge sclk) begin
    if (rcmd_1a) begin
      rdat0_2a <= dat[rwidx_1a].dat0;
      rdat1_2a <= dat[rwidx_1a].dat1;
      rdat_val_2a <= dat[rwidx_1a].valid;
      XCHK_RWIDX_R: assert(~$isunknown(rwidx_1a)) else $display("RWIDX_R rwidx_1a is X");
    end
    XCHK_RCMD: assert(~$isunknown(rcmd_1a)) else $display("Read commmand rcmd_1a is X");
  end

endmodule

module encoder_m
  (/*AUTOARG*/
  // Outputs
  hit, multihit, index,
  // Inputs
  match
  );
   parameter N = 5;
   parameter W = $clog2(N);
   output logic hit;
   output logic multihit;
   output logic [W-1:0] index;
   input [N-1:0] 	match;

   logic [W-1:0] 	index_n;
   always_comb begin
      index = 0;
      index_n = 0;
      for (int i = 0; i < N; i++) begin
	 index    = index   | {W{match[i]}} &  i[W-1:0];
	 index_n  = index_n | {W{match[i]}} & ~i[W-1:0];
      end
   end

   assign hit = |{index, index_n};
   assign multihit = hit & (index != ~index_n);
endmodule

// Local Variables:
// mode:verilog
// fill-column:132
// verilog-auto-delete-trailing-whitespace:t
// verilog-indent-level-behavioral:2
// verilog-indent-level-declaration:2
// verilog-indent-level-directive:2
// verilog-indent-level-module:2
// verilog-indent-level:2
// verilog-library-flags:("-f project/dvconf/vc/input_autos.vc")
// End:
// ************************************************************************
// *                                                                      *
// *  CAVIUM CONFIDENTIAL AND PROPRIETARY NOTE                            *
// *                                                                      *
// *  This software contains information confidential and proprietary     *
// *  to Cavium, Inc. It shall not be reproduced in whole or in part,     *
// *  or transferred to other documents, or disclosed to third parties,   *
// *  or used for any purpose other than that for which it was obtained,  *
// *  without the prior written consent of Cavium, Inc.                   *
// *                                                                      *
// *  Copyright 2017, Cavium, Inc.  All rights reserved.                  *
// *                                                                      *
// ************************************************************************
// * Author      : dfenton
// * Description : Multihit resolution for P1 TCAM
//    - Takes a NENT-wide vector as input
//    - If MATCH_HIGHEST == 0, finds the lowest-numbered index whose bit == 1
//    - Otherwise, finds the highest-numbered index whose bit == 1
//    - External logic is responsible to flop the input vector and output index, and to
//      ensure there is at least 1 bit valid in the input vector before accepting the output
//      index as valid.
// ************************************************************************

module p1_tcam_mhit
  #(parameter NENT=1024,  // Number of Entries
    parameter NENT_LOG2 = $clog2(NENT),
    parameter MATCH_HIGHEST = 0
    )
  (
   input logic [NENT-1:0] 	hitvec,
   output logic [NENT_LOG2-1:0] hitidx
   );

  logic [NENT_LOG2:0][NENT-1:0] tmp_hitvec;  // Not as bad as it looks; most of this will be optimized away...

  assign tmp_hitvec[0] = hitvec;

  // Trying to do this in 1 650MHz cycle for now... will be tight with a 1024b input vector
  // Hopefully the tools are smart enough to infer a feedforward tree of ORs rather than actually implementing the tmp_hitvec shift
  // operations written here. If not, we can explicitly code the feedforward tree later.
  generate
    genvar                     ii;     
    if (MATCH_HIGHEST == 0) begin : low
      // Find the lowest-numbered hit index
      // Note that if hitvec == '0, this code will return an (irrelevant) index value of '1
      for (ii = 0; ii < NENT_LOG2; ii++) begin : nent1
	assign hitidx[NENT_LOG2-1-ii] = (|tmp_hitvec[ii][(1<<(NENT_LOG2-1-ii))-1:0]) ? 1'b0 : 1'b1;
	assign tmp_hitvec[ii+1] = (hitidx[NENT_LOG2-1-ii]) ? (tmp_hitvec[ii] >> (1<<(NENT_LOG2-1-ii))) : tmp_hitvec[ii];
      end
    end
    else begin : high
      // Find the highest-numbered hit index
      // Note that if hitvec == '0, this code will return an (irrelevant) index value of '0
      for (ii = 0; ii < NENT_LOG2; ii++) begin : nent2
	assign hitidx[NENT_LOG2-1-ii] = (|tmp_hitvec[ii][NENT-1:NENT-(1<<(NENT_LOG2-1-ii))]) ? 1'b1 : 1'b0;
	assign tmp_hitvec[ii+1] = (hitidx[NENT_LOG2-1-ii]) ? tmp_hitvec[ii] : (tmp_hitvec[ii] << (1<<(NENT_LOG2-1-ii)));
      end
    end
  endgenerate

endmodule

// Local Variables:
// mode:verilog
// fill-column:132
// verilog-auto-delete-trailing-whitespace:t
// verilog-indent-level-behavioral:2
// verilog-indent-level-declaration:2
// verilog-indent-level-directive:2
// verilog-indent-level-module:2
// verilog-indent-level:2
// verilog-library-flags:("-f project/dvconf/vc/input_autos.vc")
// End:

`ifndef membus_out_width
  `define membus_out_width 2
  `define membus_in_width 2
`endif

// ************************************************************************
// *                                                                      *
// *  CAVIUM CONFIDENTIAL AND PROPRIETARY NOTE                            *
// *                                                                      *
// *  This software contains information confidential and proprietary     *
// *  to Cavium, Inc. It shall not be reproduced in whole or in part,     *
// *  or transferred to other documents, or disclosed to third parties,   *
// *  or used for any purpose other than that for which it was obtained,  *
// *  without the prior written consent of Cavium, Inc.                   *
// *                                                                      *
// *  Copyright 2017, Cavium, Inc.  All rights reserved.                  *
// *                                                                      *
// ************************************************************************
// * Author      : dfenton
// * Description : Wrapper for ternary CAM model, allowing for p1-specific signal naming
// ************************************************************************

module p1_tcam_wrap
  #(parameter NENT=1024,  // Number of Entries
    parameter WIDTH=135,  // Cam width including the valid bit
    parameter NENT_LOG2 = $clog2(NENT),
    parameter MATCH_HIGHEST = 0
    )
  (
   // ----------------------------------------------------------------------
   // Misc clocking and control signals
   // ----------------------------------------------------------------------

   input 			clk,
   //input 			tsw_defs::mdh_tsw_t dft_in,
   //output 			tsw_defs::tsw_mdh_t dft_out,
   input [`membus_in_width-1:0] dft_in,
   output [`membus_out_width-1:0] dft_out,

   // ----------------------------------------------------------------------
   // CAM Lookup Interface
   // ----------------------------------------------------------------------

   input 			ccmd_0a, //Cam cmd
   input 			icmd_0a, //Inval cmd. Use this to inval the whole cam at once
   input [WIDTH-2:0] 		cdat_0a, //Looked up key
   input [WIDTH-2:0] 		cmsk_0a, //Mask assosiated with the key
   output logic [NENT-1:0] 	hitvec_1a, //raw hit outputs
   output logic [NENT_LOG2-1:0] hitidx_1a, //encoded hit (only accurate if !multihit_1a)
   output logic 		hit_1a, //if cam hits
   output logic 		multihit_1a, // if cam has multihits. hitidx_1a will be garbage then
   output logic [NENT_LOG2-1:0] hitidx_2a, // encoded hit (lowest-numbered index that was hit if MATCH_HIGHEST == 0, highest-numbered index otherwise)
   output logic 		hit_2a, //if cam hits; hitidx_2a will be valid, even after a multihit

   // ----------------------------------------------------------------------
   // RD/WR interface
   // ----------------------------------------------------------------------
   //
   input 			rcmd_0a, //rd cmd
   input 			wcmd_0a, //wr cmd
   input [WIDTH-2:0] 		wdat_0a,
   input [WIDTH-2:0] 		wmsk_0a,
   input 			wdat_val_0a, //valid bit
   input [NENT_LOG2-1:0] 	rwidx_0a, //rd/wr index
   output logic [WIDTH-2:0] 	rdat_2a,
   output logic [WIDTH-2:0] 	rdat0_2a, //read of cell 0 of tcam cell {~dat & ~mask} //Encoded read data needed for Bug# 31206
   output logic [WIDTH-2:0] 	rmsk_2a,
   output logic 		rdat_val_2a //read valid bit
   );

  logic [NENT-1:0] 		hitvec_2a;
  logic [NENT_LOG2:0][NENT-1:0] tmp_hitvec;  // Not as bad as it looks; most of this will be optimized away...

  // ----------------------------------------------------------------------
  // Logic to figure out first or last match in the event of multihit
  // ----------------------------------------------------------------------

  always_ff @(posedge clk) begin
    hit_2a    <= hit_1a;
    hitvec_2a <= (hit_1a) ? hitvec_1a : '0;
  end

  /* p1_tcam_mhit AUTO_TEMPLATE (
   .hit\(.*\)   (hit\1_2a[]),
   );*/

  p1_tcam_mhit #(/*AUTOINSTPARAM*/
		 // Parameters
		 .NENT			(NENT),
		 .NENT_LOG2		(NENT_LOG2),
		 .MATCH_HIGHEST		(MATCH_HIGHEST))
  p1_tcam_mhit(/*AUTOINST*/
	       // Outputs
	       .hitidx			(hitidx_2a[NENT_LOG2-1:0]), // Templated
	       // Inputs
	       .hitvec			(hitvec_2a[NENT-1:0]));	 // Templated

  // ----------------------------------------------------------------------
  // CAM instantiation. Behavioral model for PA development, real thing for P1
  // ----------------------------------------------------------------------


  cam_ternary_beh
    #(/*AUTOINSTPARAM*/
      // Parameters
      .NENT				(NENT),
      .WIDTH				(WIDTH),
      .NENT_LOG2			(NENT_LOG2))
  cam_135w1024
    (/*AUTOINST*/
     // Outputs
     .scan_out_sclk			(),			 // Templated
     .hitvec_1a				(hitvec_1a[NENT-1:0]),
     .hitidx_1a				(hitidx_1a[NENT_LOG2-1:0]),
     .hit_1a				(hit_1a),
     .multihit_1a			(multihit_1a),
     .rdat_2a				(rdat_2a[WIDTH-2:0]),
     .rdat0_2a				(),			 // Templated
     .rmsk_2a				(rmsk_2a[WIDTH-2:0]),
     .rdat_val_2a			(rdat_val_2a),
     // Inputs
     .sclk				(clk),			 // Templated
     .scan_mode				(1'b0),			 // Templated
     .se_in				(1'b0),			 // Templated
     .scan_in_sclk			(1'b0),			 // Templated
     .ccmd_0a				(ccmd_0a),
     .icmd_0a				(icmd_0a),
     .cdat_0a				(cdat_0a[WIDTH-2:0]),
     .cmsk_0a				(cmsk_0a[WIDTH-2:0]),
     .rcmd_0a				(rcmd_0a),
     .wcmd_0a				(wcmd_0a),
     .wdat_0a				(wdat_0a[WIDTH-2:0]),
     .wmsk_0a				(wmsk_0a[WIDTH-2:0]),
     .wdat_val_0a			(wdat_val_0a),
     .rwidx_0a				(rwidx_0a[NENT_LOG2-1:0]));

endmodule

