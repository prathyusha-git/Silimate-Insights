module design_logic_combo_3_3(input logic a,b,c, output logic y);
  assign y = (a ^ b) ^ c;
endmodule
