`timescale 1ns/1ps

module analog_ip (
  input              CH0_IN,
  input              CH1_IN,
  input              CH2_IN,
  input              CH3_IN,
  output             TEST_OUT,
  inout              USB0_DM,
  inout              USB0_DP,
  input              sys_clock,    // 200 MHz
  input              bus_clock,    // 100 MHz
  input              resetn,
  input              stop,
  input       [1:0]  mem_ahb_htrans,
  input              mem_ahb_hready,
  input              mem_ahb_hwrite,
  input       [31:0] mem_ahb_haddr,
  input       [2:0]  mem_ahb_hsize,
  input       [2:0]  mem_ahb_hburst,
  input       [31:0] mem_ahb_hwdata,
  output tri1        mem_ahb_hreadyout,
  output tri0        mem_ahb_hresp,
  output      [31:0] mem_ahb_hrdata,
  output tri0        slave_ahb_hsel,
  output tri1        slave_ahb_hready,
  input              slave_ahb_hreadyout,
  output tri0 [1:0]  slave_ahb_htrans,
  output tri0 [2:0]  slave_ahb_hsize,
  output tri0 [2:0]  slave_ahb_hburst,
  output tri0        slave_ahb_hwrite,
  output tri0 [31:0] slave_ahb_haddr,
  output tri0 [31:0] slave_ahb_hwdata,
  input              slave_ahb_hresp,
  input       [31:0] slave_ahb_hrdata,
  output tri0 [3:0]  ext_dma_DMACBREQ,
  output tri0 [3:0]  ext_dma_DMACLBREQ,
  output tri0 [3:0]  ext_dma_DMACSREQ,
  output tri0 [3:0]  ext_dma_DMACLSREQ,
  input       [3:0]  ext_dma_DMACCLR,
  input       [3:0]  ext_dma_DMACTC,
  output tri0 [3:0]  local_int
);

  assign slave_ahb_hready = 1'b1;

  // -------------------------------------------------------------------------
  // 1. Built-in Hardware Square Wave Test Generator (PIN_11)
  // Default ~100 kHz square wave: 200MHz / (2 * 1000) = 100 kHz
  // -------------------------------------------------------------------------
  reg [15:0] test_clk_div = 16'd0;
  reg [15:0] test_div_limit = 16'd999;
  reg        test_wave_reg = 1'b0;
  reg        test_en = 1'b1;

  always @(posedge sys_clock or negedge resetn) begin
    if (!resetn) begin
      test_clk_div  <= 16'd0;
      test_wave_reg <= 1'b0;
    end else if (test_en) begin
      if (test_clk_div >= test_div_limit) begin
        test_clk_div  <= 16'd0;
        test_wave_reg <= ~test_wave_reg;
      end else begin
        test_clk_div <= test_clk_div + 16'd1;
      end
    end else begin
      test_wave_reg <= 1'b0;
    end
  end

  assign TEST_OUT = test_wave_reg;

  // -------------------------------------------------------------------------
  // 2. Hardware Sampler Core (Synchronous CPLD Fabric Sampling)
  // Input channels CH0..CH3
  // -------------------------------------------------------------------------
  wire [3:0] ch_raw = {CH3_IN, CH2_IN, CH1_IN, CH0_IN};

  reg        sampler_arm = 1'b0;
  reg        sampler_force = 1'b0;
  reg [3:0]  trig_mask = 4'd0;
  reg [3:0]  trig_val  = 4'd0;
  reg        trig_edge_en = 1'b0;
  reg [15:0] sample_depth_words = 16'd1024; // 1024 words * 8 = 8192 samples
  reg [7:0]  sample_clk_div = 8'd0;

  reg        busy = 1'b0;
  reg        done = 1'b0;
  reg        triggered = 1'b0;
  reg [7:0]  div_cnt = 8'd0;
  reg [2:0]  sub_idx = 3'd0;
  reg [31:0] shift_buf = 32'd0;
  reg [15:0] word_idx = 16'd0;

  // Dual-Port Block RAM: 1024 words x 32-bit = 32 Kbits
  reg [31:0] ram [0:1023];
  reg [9:0]  ram_wr_addr = 10'd0;
  reg [31:0] ram_wr_data = 32'd0;
  reg        ram_wr_en   = 1'b0;

  always @(posedge sys_clock) begin
    if (ram_wr_en) begin
      ram[ram_wr_addr] <= ram_wr_data;
    end
  end

  // Edge & Level Trigger Engine
  reg [3:0] ch_prev = 4'd0;
  always @(posedge sys_clock) begin
    ch_prev <= ch_raw;
  end

  // Level match: (ch_raw & mask) == (val & mask)
  // Edge match (when bit 12 of REG_CTRL is set):
  //   if trig_val bit is 1 -> Rising Edge: (ch_prev==0 && ch_raw==1)
  //   if trig_val bit is 0 -> Falling Edge: (ch_prev==1 && ch_raw==0)
  wire [3:0] ch_rising  = (~ch_prev) & ch_raw;
  wire [3:0] ch_falling = ch_prev & (~ch_raw);
  wire [3:0] ch_edge    = (ch_rising & trig_val) | (ch_falling & ~trig_val);
  
  wire trig_edge_mode = trig_edge_en;
  wire trig_match = trig_edge_mode ? (| (ch_edge & trig_mask)) : (((ch_raw & trig_mask) == (trig_val & trig_mask)));

  always @(posedge sys_clock or negedge resetn) begin
    if (!resetn) begin
      busy        <= 1'b0;
      done        <= 1'b0;
      triggered   <= 1'b0;
      div_cnt     <= 8'd0;
      sub_idx     <= 3'd0;
      shift_buf   <= 32'd0;
      word_idx    <= 16'd0;
      ram_wr_en   <= 1'b0;
    end else begin
      ram_wr_en <= 1'b0;

      if (!sampler_arm) begin
        busy      <= 1'b0;
        done      <= 1'b0;
        triggered <= 1'b0;
        div_cnt   <= 8'd0;
        sub_idx   <= 3'd0;
        word_idx  <= 16'd0;
      end else if (busy) begin
        if (div_cnt < sample_clk_div) begin
          div_cnt <= div_cnt + 8'd1;
        end else begin
          div_cnt <= 8'd0;
          shift_buf <= {ch_raw, shift_buf[31:4]};
          sub_idx   <= sub_idx + 3'd1;

          if (sub_idx == 3'd7) begin
            ram_wr_data <= {ch_raw, shift_buf[31:4]};
            ram_wr_addr <= word_idx[9:0];
            ram_wr_en   <= 1'b1;
            word_idx    <= word_idx + 16'd1;

            if (word_idx >= sample_depth_words - 16'd1) begin
              busy <= 1'b0;
              done <= 1'b1;
            end
          end
        end
      end else if (!done) begin
        if (sampler_force || trig_mask == 4'd0 || trig_match) begin
          triggered <= 1'b1;
          busy      <= 1'b1;
          div_cnt   <= 8'd0;
          sub_idx   <= 3'd0;
          word_idx  <= 16'd0;
        end
      end
    end
  end

  // -------------------------------------------------------------------------
  // 3. AHB to APB Bridge & APB Register / Memory Bus
  // -------------------------------------------------------------------------
  wire        apb_psel;
  wire        apb_penable;
  wire        apb_pwrite;
  wire [31:0] apb_paddr;
  wire [31:0] apb_pwdata;
  wire [3:0]  apb_pstrb;
  wire [2:0]  apb_pprot;
  wire        apb_pready  = 1'b1;
  wire        apb_pslverr = 1'b0;
  reg  [31:0] apb_prdata;

  ahb2apb #(32, 32) ahb2apb_inst (
    .reset        (!resetn           ),
    .ahb_clock    (sys_clock         ),
    .ahb_hmastlock(1'b0              ),
    .ahb_htrans   (mem_ahb_htrans    ),
    .ahb_hsel     (1'b1              ),
    .ahb_hready   (mem_ahb_hready    ),
    .ahb_hwrite   (mem_ahb_hwrite    ),
    .ahb_haddr    (mem_ahb_haddr     ),
    .ahb_hsize    (mem_ahb_hsize     ),
    .ahb_hburst   (mem_ahb_hburst    ),
    .ahb_hprot    (4'b0011           ),
    .ahb_hwdata   (mem_ahb_hwdata    ),
    .ahb_hrdata   (mem_ahb_hrdata    ),
    .ahb_hreadyout(mem_ahb_hreadyout ),
    .ahb_hresp    (mem_ahb_hresp     ),
    .apb_clock    (bus_clock         ),
    .apb_psel     (apb_psel          ),
    .apb_penable  (apb_penable       ),
    .apb_pwrite   (apb_pwrite        ),
    .apb_paddr    (apb_paddr         ),
    .apb_pwdata   (apb_pwdata        ),
    .apb_pstrb    (apb_pstrb         ),
    .apb_pprot    (apb_pprot         ),
    .apb_pready   (apb_pready        ),
    .apb_pslverr  (apb_pslverr       ),
    .apb_prdata   (apb_prdata        )
  );

  wire apb_access = apb_psel && apb_penable;

  // APB Write
  always @(posedge bus_clock or negedge resetn) begin
    if (!resetn) begin
      sampler_arm        <= 1'b0;
      sampler_force      <= 1'b0;
      trig_mask          <= 4'd0;
      trig_val           <= 4'd0;
      sample_clk_div     <= 8'd0;
      sample_depth_words <= 16'd1024;
      test_en            <= 1'b1;
      test_div_limit     <= 16'd999;
    end else if (apb_access && apb_pwrite) begin
      case (apb_paddr[15:0])
        16'h0000: begin // 0x60000000: REG_CTRL
          sampler_arm    <= apb_pwdata[0];
          sampler_force  <= apb_pwdata[2];
          test_en        <= apb_pwdata[3];
          trig_mask      <= apb_pwdata[7:4];
          trig_val       <= apb_pwdata[11:8];
          sample_clk_div <= apb_pwdata[23:16];
        end
        16'h0008: begin // 0x60000008: REG_DEPTH
          if (apb_pwdata[15:0] > 16'd0 && apb_pwdata[15:0] <= 16'd1024)
            sample_depth_words <= apb_pwdata[15:0];
          else
            sample_depth_words <= 16'd1024;
        end
        16'h000C: begin // 0x6000000C: REG_TEST_DIV
          test_div_limit <= apb_pwdata[15:0];
        end
        default: ;
      endcase
    end
  end

  // APB Read
  reg [31:0] ram_rd_port;
  always @(posedge bus_clock) begin
    ram_rd_port <= ram[apb_paddr[11:2]];
  end

  always @(*) begin
    if (apb_paddr[15:12] >= 4'h1) begin
      apb_prdata = ram_rd_port;
    end else begin
      case (apb_paddr[15:0])
        16'h0000: apb_prdata = {8'h0, sample_clk_div, 4'h0, trig_val, trig_mask, 1'b0, test_en, sampler_force, 1'b0, sampler_arm};
        16'h0004: apb_prdata = {word_idx, 13'h0, triggered, done, busy};
        16'h0008: apb_prdata = {16'h0, sample_depth_words};
        16'h000C: apb_prdata = {16'h0, test_div_limit};
        16'h0010: apb_prdata = 32'h4C413332; // "LA32" magic ID
        default:  apb_prdata = 32'h0;
      endcase
    end
  end

endmodule