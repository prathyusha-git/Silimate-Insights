module rewrite_small_fsm_17(input logic clk, rst_n, in, output logic out);
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
      S0: begin
        if (in) ns = S1;
        else ns = S0;
      end
      S1: begin
        if (in) ns = S2;
        else ns = S0;
      end
      S2: begin
        out = 1'b1;
        if (in) ns = S3;
        else ns = S0;
      end
      default: begin
        if (in) ns = S3;
        else ns = S0;
      end
    endcase
  end
endmodule
