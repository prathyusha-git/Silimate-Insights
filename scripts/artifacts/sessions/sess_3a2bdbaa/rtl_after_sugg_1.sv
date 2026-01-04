module rewrite_logic_combo_1_47(input logic a,b,c, output logic y);
  logic t;
  assign t = a & b;
  assign y = t | c;
endmodule
