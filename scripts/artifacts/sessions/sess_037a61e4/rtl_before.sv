module design_logic_combo_3_16(input logic a,b,c, output logic y);
  assign y = (a ^ b) ^ c;
endmodule
