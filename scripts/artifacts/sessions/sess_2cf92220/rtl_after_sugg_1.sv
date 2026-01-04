module rewrite_logic_combo_3_7(input logic a,b,c, output logic y);
  logic t;
  assign t = a ^ b;
  assign y = t ^ c;
endmodule
