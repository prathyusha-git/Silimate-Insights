module design_logic_combo_3_23(input logic a,b,c, output logic y);
  assign y = (a ^ b) ^ c;
endmodule
