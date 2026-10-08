	imescale 1ns/1ps

module la_sampler #(
  parameter BUFFER_WORDS = 2048 // 2048 words * 8 samples/word = 16,384 samples (or BRAM based)
) (
  input             clk,          // High speed sampling clock (100MHz / 200MHz)
  input             rst_n,        // Active-low synchronous reset
  input      [3:0]  ch_in,        // 4-Channel input: CH0..CH3
  input             arm,          // MCU arm capture signal
  input      [3:0]  trig_mask,    // Channel trigger mask
  input      [3:0]  trig_val,     // Channel trigger value
  input      [15:0] sample_depth, // Target number of 32-bit words to capture

  output reg        busy,         // 1 while sampling
  output reg        done,         // Pulse/level when buffer filled
  output reg [11:0] wr_addr,      // Buffer write pointer
  output reg [31:0] wr_data,      // Packed sample word (8 samples of 4-bit)
  output reg        wr_en         // Buffer write enable
);

  reg [2:0]  sample_sub_idx;
  reg [31:0] shift_reg;
  reg        triggered;
  reg [15:0] word_counter;
  reg [3:0]  ch_prev;

  wire trig_match = ((ch_in & trig_mask) == (trig_val & trig_mask));

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      busy           <= 1'b0;
      done           <= 1'b0;
      triggered      <= 1'b0;
      sample_sub_idx <= 3'd0;
      shift_reg      <= 32'd0;
      word_counter   <= 16'd0;
      wr_addr        <= 12'd0;
      wr_data        <= 32'd0;
      wr_en          <= 1'b0;
      ch_prev        <= 4'd0;
    end else begin
      ch_prev <= ch_in;
      wr_en   <= 1'b0;

      if (!arm) begin
        busy           <= 1'b0;
        done           <= 1'b0;
        triggered      <= 1'b0;
        sample_sub_idx <= 3'd0;
        word_counter   <= 16'd0;
        wr_addr        <= 12'd0;
      end else if (busy) begin
        // Pack 4-bit input into 32-bit shift register
        shift_reg <= {shift_reg[27:0], ch_in};
        sample_sub_idx <= sample_sub_idx + 1'b1;

        if (sample_sub_idx == 3'd7) begin
          wr_data      <= {shift_reg[27:0], ch_in};
          wr_addr      <= word_counter[11:0];
          wr_en        <= 1'b1;
          word_counter <= word_counter + 1'b1;

          if (word_counter >= sample_depth - 1'b1) begin
            busy <= 1'b0;
            done <= 1'b1;
          end
        end
      end else if (!done) begin
        // Waiting for trigger
        if (trig_mask == 4'd0 || trig_match) begin
          triggered <= 1'b1;
          busy      <= 1'b1;
          sample_sub_idx <= 3'd0;
          word_counter   <= 16'd0;
        end
      end
    end
  end

endmodule
