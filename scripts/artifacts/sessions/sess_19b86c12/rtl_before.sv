module design_logic_combo_2_42(input logic a,b,c, output logic y);
  assign y = (a | b) & (~c);
endmodule
