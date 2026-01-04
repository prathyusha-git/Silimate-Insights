module rewrite_mux_41(input logic sel, d0, d1, output logic y);
  assign y = (~sel & d0) | (sel & d1);
endmodule
