module design_mux_38(input logic sel, d0, d1, output logic y);
  assign y = sel ? d1 : d0;
endmodule
