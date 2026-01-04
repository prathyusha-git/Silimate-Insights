module design_small_fsm_19(input logic clk, rst_n, in, output logic out);
  typedef enum logic [1:0] {S0, S1, S2, S3} state_t;
  state_t s, ns;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) s <= S0;
    else s <= ns;
  end

  always_comb begin
    ns = s;
    out = 1'b0;
    unique case (s)
      S0: ns = in ? S1 : S0;
      S1: ns = in ? S2 : S0;
      S2: begin ns = in ? S3 : S0; out = 1'b1; end
      S3: ns = in ? S3 : S0;
    endcase
  end
endmodule
