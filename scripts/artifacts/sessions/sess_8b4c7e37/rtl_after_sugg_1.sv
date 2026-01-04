module rewrite_adder4_2(input logic [3:0] a,b, output logic [4:0] y);
  logic [4:0] aa, bb;
  assign aa = {1'b0,a};
  assign bb = {1'b0,b};
  assign y = aa + bb;
endmodule
