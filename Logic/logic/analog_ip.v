`timescale 1ns/1ps

module analog_ip (
  input              CH0_IN,
  input              CH1_IN,
  input              CH2_IN,
  input              CH3_IN,
  output             SG_OUT,
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
  // 1. Digital Square Wave Generator (PIN_5, selected by P5_CFG[8])
  //    f = 100 MHz / ((A + 1) * (B + 1)); A/B are 16-bit reload values.
  //    Two cascaded down-counters keep every comparator a short 16-bit
  //    zero-detect (no wide equality compares), so the 200 MHz domain stays
  //    comfortably timed.  A = 0/B = 0 -> 100 MHz;  A = 999/B = 0 -> 100 kHz.
  //    REG_SQ_DIV[15:0] = A, REG_SQ_DIV[31:16] = B.
  // -------------------------------------------------------------------------
  reg [15:0] sq_rl_a = 16'd999;
  reg [15:0] sq_rl_b = 16'd0;
  reg [15:0] sq_cnt_a = 16'd0;
  reg [15:0] sq_cnt_b = 16'd0;
  reg        test_wave_reg = 1'b0;
  reg        test_en = 1'b1;

  wire sq_a_zero    = (sq_cnt_a == 16'd0);
  wire sq_b_zero    = (sq_cnt_b == 16'd0);
  wire sq_both_zero = sq_a_zero & sq_b_zero;

  always @(posedge sys_clock or negedge resetn) begin
    if (!resetn) begin
      sq_cnt_a      <= 16'd0;
      sq_cnt_b      <= 16'd0;
      test_wave_reg <= 1'b0;
    end else if (test_en) begin
      if (sq_both_zero) begin
        sq_cnt_a      <= sq_rl_a;
        sq_cnt_b      <= sq_rl_b;
        test_wave_reg <= ~test_wave_reg;
      end else if (sq_a_zero) begin
        sq_cnt_a <= sq_rl_a;
        sq_cnt_b <= sq_cnt_b - 16'd1;
      end else begin
        sq_cnt_a <= sq_cnt_a - 16'd1;
      end
    end else begin
      test_wave_reg <= 1'b0;
    end
  end

  // -------------------------------------------------------------------------
  // 1b. PIN_5 Trigger / Pulse Engine (bus_clock domain, 10 ns base tick)
  //     P5_CFG[1:0] mode : 0 = delay -> level, 1 = delay -> pulse,
  //                        2 = host -> level,  3 = host -> pulse
  //     P5_CFG[2]   level    : active output level (1 = high)
  //     P5_CFG[3]   idle     : idle output level
  //     P5_CFG[5:4] prescale : tick = 10 ns * 10^prescale (1/10/100/1000)
  //     P5_CFG[8]   sq_sel   : 1 = square-wave source (default), 0 = engine
  //     P5_CTRL[0]  arm   : rising edge starts the sequence (delay modes)
  //     P5_CTRL[1]  fire  : immediate software trigger (host modes / manual)
  //     P5_CTRL[2]  clear : reset engine and done flag
  // -------------------------------------------------------------------------
  reg [1:0]  p5_mode     = 2'd0;
  reg        p5_level    = 1'b1;
  reg        p5_idle     = 1'b0;
  reg [1:0]  p5_prescale = 2'd0;
  reg        p5_sq_sel   = 1'b1;
  reg [31:0] p5_delay    = 32'd0;
  reg [31:0] p5_width    = 32'd10;
  reg        p5_arm      = 1'b0;
  reg        p5_arm_d    = 1'b0;
  reg [2:0]  p5_state    = 3'd0;
  reg        p5_out      = 1'b0;
  reg        p5_busy     = 1'b0;
  reg        p5_done     = 1'b0;
  reg [31:0] p5_cnt      = 32'd0;
  reg [31:0] p5_psc_cnt  = 32'd0;

  wire p5_write      = apb_access && apb_pwrite && (apb_paddr[15:12] == 4'h0);
  wire p5_fire_now   = p5_write && (apb_paddr[15:0] == 16'h002C) && apb_pwdata[1];
  wire p5_clear_now  = p5_write && (apb_paddr[15:0] == 16'h002C) && apb_pwdata[2];
  wire p5_arm_rise   = p5_arm & ~p5_arm_d;
  wire p5_delay_mode = ~p5_mode[1];
  wire p5_start      = p5_fire_now | (p5_arm_rise & p5_delay_mode);
  wire [31:0] p5_tick_limit = (p5_prescale == 2'd0) ? 32'd0  :
                              (p5_prescale == 2'd1) ? 32'd9  :
                              (p5_prescale == 2'd2) ? 32'd99 : 32'd999;
  wire p5_tick       = (p5_psc_cnt >= p5_tick_limit);

  always @(posedge bus_clock or negedge resetn) begin
    if (!resetn) begin
      p5_mode     <= 2'd0;
      p5_level    <= 1'b1;
      p5_idle     <= 1'b0;
      p5_prescale <= 2'd0;
      p5_sq_sel   <= 1'b1;
      p5_delay    <= 32'd0;
      p5_width    <= 32'd10;
      p5_arm      <= 1'b0;
      p5_arm_d    <= 1'b0;
      p5_state    <= 3'd0;
      p5_out      <= 1'b0;
      p5_busy     <= 1'b0;
      p5_done     <= 1'b0;
      p5_cnt      <= 32'd0;
      p5_psc_cnt  <= 32'd0;
    end else begin
      // Register writes
      if (p5_write) begin
        case (apb_paddr[15:0])
          16'h0020: begin
            p5_mode     <= apb_pwdata[1:0];
            p5_level    <= apb_pwdata[2];
            p5_idle     <= apb_pwdata[3];
            p5_prescale <= apb_pwdata[5:4];
            p5_sq_sel   <= apb_pwdata[8];
          end
          16'h0024: p5_delay <= apb_pwdata;
          16'h0028: p5_width <= apb_pwdata;
          16'h002C: p5_arm   <= apb_pwdata[0];
          default: ;
        endcase
      end
      p5_arm_d <= p5_arm;

      // Tick prescaler
      if (p5_tick) p5_psc_cnt <= 32'd0;
      else         p5_psc_cnt <= p5_psc_cnt + 32'd1;

      // Output engine FSM
      if (p5_sq_sel) begin
        p5_state <= 3'd0;
        p5_busy  <= 1'b0;
        p5_out   <= p5_idle;
        p5_cnt   <= 32'd0;
      end else if (p5_clear_now) begin
        p5_state <= 3'd0;
        p5_busy  <= 1'b0;
        p5_done  <= 1'b0;
        p5_out   <= p5_idle;
        p5_cnt   <= 32'd0;
      end else begin
        case (p5_state)
          3'd0: begin // IDLE: wait for start
            p5_out <= p5_idle;
            if (p5_start) begin
              p5_done <= 1'b0;
              if (p5_delay == 32'd0) begin
                p5_out <= p5_level;
                if (p5_mode[0]) begin
                  p5_state <= 3'd2;
                  p5_cnt   <= (p5_width == 32'd0) ? 32'd0 : (p5_width - 32'd1);
                  p5_busy  <= 1'b1;
                end else begin
                  p5_state <= 3'd3;
                  p5_done  <= 1'b1;
                end
              end else begin
                p5_state <= 3'd1;
                p5_cnt   <= p5_delay - 32'd1;
                p5_busy  <= 1'b1;
              end
            end
          end
          3'd1: begin // DELAY countdown
            if (p5_tick) begin
              if (p5_cnt == 32'd0) begin
                p5_out <= p5_level;
                if (p5_mode[0]) begin
                  p5_state <= 3'd2;
                  p5_cnt   <= (p5_width == 32'd0) ? 32'd0 : (p5_width - 32'd1);
                end else begin
                  p5_state <= 3'd3;
                  p5_busy  <= 1'b0;
                  p5_done  <= 1'b1;
                end
              end else begin
                p5_cnt <= p5_cnt - 32'd1;
              end
            end
          end
          3'd2: begin // PULSE: hold active level for p5_width ticks
            if (p5_tick) begin
              if (p5_cnt == 32'd0) begin
                p5_out   <= p5_idle;
                p5_state <= 3'd0;
                p5_busy  <= 1'b0;
                p5_done  <= 1'b1;
              end else begin
                p5_cnt <= p5_cnt - 32'd1;
              end
            end
          end
          3'd3: begin // LEVEL HOLD: keep level until clear or restart
            if (p5_start) begin
              p5_done <= 1'b0;
              if (p5_delay == 32'd0) begin
                p5_out <= p5_level;
              end else begin
                p5_state <= 3'd1;
                p5_cnt   <= p5_delay - 32'd1;
                p5_busy  <= 1'b1;
                p5_out   <= p5_idle;
              end
            end else begin
              p5_out  <= p5_level;
              p5_busy <= 1'b0;
              p5_done <= 1'b1;
            end
          end
          default: p5_state <= 3'd0;
        endcase
      end
    end
  end

  assign SG_OUT = p5_sq_sel ? test_wave_reg : p5_out;

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
  reg [15:0] sample_clk_div = 16'd0;

  reg        busy = 1'b0;
  reg        done = 1'b0;
  reg        triggered = 1'b0;
  reg [15:0] div_cnt = 16'd0;
  reg [2:0]  sub_idx = 3'd0;
  reg [31:0] shift_buf = 32'd0;
  reg [15:0] word_idx = 16'd0;
  reg [9:0]  trig_pos = 10'd0;
  reg [9:0]  wr_ptr   = 10'd0;
  reg [15:0] post_trig_words = 16'd1024;
  reg [15:0] post_cnt = 16'd0;


  // Dual-Port Block RAM: 1024 words x 32-bit = 32 Kbits
  reg [31:0] ram [0:1023];
  reg [9:0]  ram_wr_addr = 10'd0;
  reg [31:0] ram_wr_data = 32'd0;
  reg        ram_wr_en   = 1'b0;

  always @(posedge bus_clock) begin
    if (ram_wr_en) begin
      ram[ram_wr_addr] <= ram_wr_data;
    end
  end

  // 2-Stage Synchronizer & Edge/Level Trigger Pipeline for STA Timing Convergence
  reg [3:0] ch_sync0 = 4'd0;
  reg [3:0] ch_sync1 = 4'd0;
  reg [3:0] ch_prev  = 4'd0;

  always @(posedge bus_clock) begin
    ch_sync0 <= ch_raw;
    ch_sync1 <= ch_sync0;
    ch_prev  <= ch_sync1;
  end

  wire [3:0] ch_current = ch_sync1;

  // Level match: (ch_current & mask) == (val & mask)
  // Edge match (when bit 12 of REG_CTRL is set):
  //   if trig_val bit is 1 -> Rising Edge: (ch_prev==0 && ch_current==1)
  //   if trig_val bit is 0 -> Falling Edge: (ch_prev==1 && ch_current==0)
  wire [3:0] ch_rising  = (~ch_prev) & ch_current;
  wire [3:0] ch_falling = ch_prev & (~ch_current);
  wire [3:0] ch_edge    = (ch_rising & trig_val) | (ch_falling & ~trig_val);
  
  wire trig_edge_mode = trig_edge_en;
  wire trig_match = trig_edge_mode ? (| (ch_edge & trig_mask)) : (((ch_current & trig_mask) == (trig_val & trig_mask)));

  // Trigger detection runs EVERY bus cycle and latches a pending flag so
  // 1-cycle edge pulses are never missed (a sample-tick-only check misses
  // edges of signals phase-locked to the sample clock, e.g. the self-test
  // wave: 10000-cycle period vs 10-cycle sample period).
  reg trig_pending = 1'b0;
  always @(posedge bus_clock or negedge resetn) begin
    if (!resetn) begin
      trig_pending <= 1'b0;
    end else if (!sampler_arm || busy) begin
      trig_pending <= 1'b0;
    end else if (sampler_force || trig_mask == 4'd0 || trig_match) begin
      trig_pending <= 1'b1;
    end
  end

  // Sample every (div+1) bus_clock cycles -> rate = 100MHz/(div+1), div up to 65535.

  always @(posedge bus_clock or negedge resetn) begin
    if (!resetn) begin
      busy      <= 1'b0;
      done      <= 1'b0;
      triggered <= 1'b0;
      div_cnt   <= 16'd0;
      sub_idx   <= 3'd0;
      shift_buf <= 32'd0;
      word_idx  <= 16'd0;
      wr_ptr    <= 10'd0;
      trig_pos  <= 10'd0;
      post_cnt  <= 16'd0;
      ram_wr_en <= 1'b0;
    end else begin
      ram_wr_en <= 1'b0;

      if (!sampler_arm) begin
        busy      <= 1'b0;
        done      <= 1'b0;
        triggered <= 1'b0;
        div_cnt   <= 16'd0;
        sub_idx   <= 3'd0;
        word_idx  <= 16'd0;
        wr_ptr    <= 10'd0;
        trig_pos  <= 10'd0;
        post_cnt  <= 16'd0;
      end else if (busy) begin
        // Sampling active: circular BRAM fill continues after the trigger;
        // post_cnt words (trigger word included) must be written before DONE.
        if (div_cnt < sample_clk_div) begin
          div_cnt <= div_cnt + 16'd1;
        end else begin
          div_cnt   <= 16'd0;
          shift_buf <= {ch_current, shift_buf[31:4]};
          sub_idx   <= sub_idx + 3'd1;
          if (sub_idx == 3'd7) begin
            ram_wr_data <= {ch_current, shift_buf[31:4]};
            ram_wr_addr <= wr_ptr;
            ram_wr_en   <= 1'b1;
            word_idx    <= word_idx + 16'd1;
            if (wr_ptr >= sample_depth_words - 16'd1) begin
              wr_ptr <= 10'd0;
            end else begin
              wr_ptr <= wr_ptr + 10'd1;
            end
            if (post_cnt >= post_trig_words - 16'd1) begin
              busy <= 1'b0;
              done <= 1'b1;
            end else begin
              post_cnt <= post_cnt + 16'd1;
            end
          end
        end
      end else if (!done) begin
        // Armed, waiting for trigger: keep sampling into the circular BRAM
        // so pre-trigger history is always available.
        if (div_cnt < sample_clk_div) begin
          div_cnt <= div_cnt + 16'd1;
        end else begin
          div_cnt   <= 16'd0;
          shift_buf <= {ch_current, shift_buf[31:4]};
          sub_idx   <= sub_idx + 3'd1;
          if (sub_idx == 3'd7) begin
            ram_wr_data <= {ch_current, shift_buf[31:4]};
            ram_wr_addr <= wr_ptr;
            ram_wr_en   <= 1'b1;
            word_idx    <= word_idx + 16'd1;
            if (wr_ptr >= sample_depth_words - 16'd1) begin
              wr_ptr <= 10'd0;
            end else begin
              wr_ptr <= wr_ptr + 10'd1;
            end
          end
          if (trig_pending) begin
            triggered <= 1'b1;
            busy      <= 1'b1;
            trig_pos  <= wr_ptr; // word index holding the trigger sample
            post_cnt  <= 16'd0;
          end
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
      sq_rl_a            <= 16'd999;
      sq_rl_b            <= 16'd0;
    end else if (apb_access && apb_pwrite) begin
      case (apb_paddr[15:0])
        16'h0000: begin // 0x60000000: REG_CTRL
          sampler_arm    <= apb_pwdata[0];
          sampler_force  <= apb_pwdata[2];
          test_en        <= apb_pwdata[3];
          trig_mask      <= apb_pwdata[7:4];
          trig_val       <= apb_pwdata[11:8];
          trig_edge_en   <= apb_pwdata[12];
          sample_clk_div <= apb_pwdata[31:16];
        end
        16'h0008: begin // 0x60000008: REG_DEPTH
          if (apb_pwdata[15:0] > 16'd0 && apb_pwdata[15:0] <= 16'd1024)
            sample_depth_words <= apb_pwdata[15:0];
          else
            sample_depth_words <= 16'd1024;
        end
        16'h000C: begin // 0x6000000C: REG_SQ_DIV  [15:0]=A [31:16]=B
          sq_rl_a <= apb_pwdata[15:0];   // f = 100 MHz / ((A + 1) * (B + 1))
          sq_rl_b <= apb_pwdata[31:16];
        end
        16'h0018: begin // 0x60000018: REG_POST_WORDS
          if (apb_pwdata[15:0] > 16'd0 && apb_pwdata[15:0] <= sample_depth_words)
            post_trig_words <= apb_pwdata[15:0];
          else
            post_trig_words <= sample_depth_words;
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
    if (apb_paddr[15:12] == 4'h1) begin
      apb_prdata = ram_rd_port;                    // 0x1000-0x1FFF: sampler BRAM
    end else if (apb_paddr[15:12] == 4'h3) begin
      apb_prdata = dac_prdata;                     // 0x3000-0x3FFF: DAC0
    end else begin
      case (apb_paddr[15:0])
        16'h0000: apb_prdata = {sample_clk_div, 3'h0, trig_edge_en, trig_val, trig_mask, test_en, sampler_force, 1'b0, sampler_arm};
        16'h0004: apb_prdata = {word_idx, 13'h0, triggered, done, busy};
        16'h0008: apb_prdata = {16'h0, sample_depth_words};
        16'h000C: apb_prdata = {sq_rl_b, sq_rl_a};   // square-wave reload A/B
        16'h0010: apb_prdata = 32'h4C413332;         // "LA32" magic ID
        16'h0014: apb_prdata = {6'h0, trig_pos, 16'h0};
        16'h0018: apb_prdata = {16'h0, post_trig_words};
        16'h0020: apb_prdata = {23'h0, p5_sq_sel, 3'h0, p5_prescale, p5_idle, p5_level, p5_mode};
        16'h0024: apb_prdata = p5_delay;
        16'h0028: apb_prdata = p5_width;
        16'h002C: apb_prdata = {29'h0, p5_out, p5_done, p5_busy};
        16'h0030: apb_prdata = p5_cnt;               // remaining ticks
        default:  apb_prdata = 32'h0;
      endcase
    end
  end

  // -------------------------------------------------------------------------
  // 4. DAC0 - PIN_11 analog waveform output (MCU DMA wave-table playback)
  //    Register base 0x60003000: CTRL [0=EN,1=BUFEN,2=DMAEN,31:16=DIV]
  //    Sample rate = 100 MHz / (DIV + 1); DMA request on EXT_DMA3 (bit 3).
  //    Hardware coordinate binding is done by the FIXED_COORD line in
  //    logic_board.asf:  macro_inst|gen_per[3].*gen_dac.dac_inst|dac_inst
  // -------------------------------------------------------------------------
  wire        dac_dma_req;
  reg         dac_dma_clr;
  wire [31:0] dac_prdata;
  wire        dac_psel    = apb_psel    && (apb_paddr[15:12] == 4'h3);
  wire        dac_penable = apb_penable && (apb_paddr[15:12] == 4'h3);

  always @(posedge bus_clock or negedge resetn) begin
    if (!resetn) dac_dma_clr <= 1'b0;
    else         dac_dma_clr <= ext_dma_DMACCLR[3];
  end

  assign ext_dma_DMACBREQ = {dac_dma_req, 3'b000};

  genvar gi;
  generate
    for (gi = 0; gi < 4; gi = gi + 1) begin : gen_per
      if (gi < 3) begin : gen_unused
        // Slots 0..2 are kept so that index 3 matches the platform DAC0
        // FIXED_COORD path (macro_inst|gen_per[3].*gen_dac.dac_inst|dac_inst).
        wire unused_slot = 1'b0;
      end else begin : gen_dac
        apb_dac dac_inst (
          .stop       (stop            ),
          .dma_req    (dac_dma_req     ),
          .dma_clr    (dac_dma_clr     ),
          .apb_clock  (bus_clock       ),
          .apb_resetn (resetn          ),
          .apb_psel   (dac_psel        ),
          .apb_penable(dac_penable     ),
          .apb_pwrite (apb_pwrite      ),
          .apb_paddr  (apb_paddr[11:0] ),
          .apb_pwdata (apb_pwdata      ),
          .apb_prdata (dac_prdata      )
        );
      end
    end
  endgenerate

endmodule

// ---------------------------------------------------------------------------
// APB DAC controller (AGM analog reference design style):
//   0x00 CTRL: [0]=EN, [1]=BUFEN, [2]=DMAEN, [31:16]=SCLK_DIV
//   0x04 DATA: [9:0] DAC code; DMA writes one sample per request
// The alta_dac hard macro is placed by Supra (FIXED_COORD) and routed to the
// dedicated DAC0 pad (PIN_11 on QFN32).
// ---------------------------------------------------------------------------
module apb_dac (
  input         stop,
  output        dma_req,
  input         dma_clr,
  input         apb_clock,
  input         apb_resetn,
  input         apb_psel,
  input         apb_penable,
  input         apb_pwrite,
  input  [11:0] apb_paddr,
  input  [31:0] apb_pwdata,
  output [31:0] apb_prdata
);
parameter SCLK_BIT = 16;

parameter ADDR_CTRL = 'h00;
parameter ADDR_DATA = 'h04;

wire apb_data_phase = apb_psel && apb_penable;

reg ctrl_dac_en, ctrl_dac_bufen, ctrl_dac_dmaen;
reg [SCLK_BIT-1:0] ctrl_sclk_div; // Sample rate = apb_clock frequency / (ctrl_sclk_div + 1)
`define DAC_CTRL_REG {ctrl_sclk_div, 13'b0, ctrl_dac_dmaen, ctrl_dac_bufen, ctrl_dac_en}

reg [9:0] dac_din;

always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) begin
    ctrl_dac_en    <= 'b0;
    ctrl_dac_bufen <= 'b0;
    ctrl_dac_dmaen <= 'b0;
    ctrl_sclk_div  <= 'b0;
  end else if (apb_data_phase && apb_pwrite && apb_paddr == ADDR_CTRL) begin
    ctrl_dac_en    <= apb_pwdata[0];
    ctrl_dac_bufen <= apb_pwdata[1];
    ctrl_dac_dmaen <= apb_pwdata[2];
    ctrl_sclk_div  <= apb_pwdata[31:16];
  end
end

always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) begin
    dac_din <= 'b0;
  end else if (apb_data_phase && apb_pwrite && apb_paddr == ADDR_DATA) begin
    dac_din <= apb_pwdata[9:0];
  end
end

wire [31:0] ctrl_read = apb_paddr == ADDR_CTRL ? `DAC_CTRL_REG : 0;
wire [31:0] data_read = apb_paddr == ADDR_DATA ? dac_din       : 0;

reg [31:0] prdata;
always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) begin
    prdata <= 32'h0;
  end else if (apb_psel && !apb_penable && !apb_pwrite) begin
    prdata <= ctrl_read | data_read;
  end
end
assign apb_prdata = prdata;

reg [SCLK_BIT-1:0] sclk_counter;
wire sclk_pulse = sclk_counter == 0;
always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) begin
    sclk_counter <= 'b0;
  end else if (!ctrl_dac_dmaen || sclk_pulse) begin
    sclk_counter <= ctrl_sclk_div;
  end else begin
    sclk_counter <= sclk_counter - 1;
  end
end

reg dma_reg;
always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) begin
    dma_reg <= 1'b0;
  end else if (!ctrl_dac_dmaen || dma_clr) begin
    dma_reg <= 1'b0;
  end else if (ctrl_dac_dmaen && sclk_pulse) begin
    dma_reg <= 1'b1;
  end
end
assign dma_req = dma_reg;

// ------------------------------------------------------------------------
// Synthesis keep-guard for the DAC hard macro:
//   `dout` is not used by the RTL (the analog signal reaches the pad inside
//   the hard macro). With a dangling output Quartus removes this instance as
//   dead logic, which also blocks the platform af_ip.tcl partition scan and
//   the Supra FIXED_COORD binding of DAC0 to PIN_11. A preserved dummy
//   register keeps the macro alive through synthesis.
// ------------------------------------------------------------------------
(* keep = 1 *) wire dac_dout; // analog output is routed to the pad inside the hard macro
(* preserve = 1 *) reg dac_dout_seen;
always @ (posedge apb_clock or negedge apb_resetn) begin
  if (!apb_resetn) dac_dout_seen <= 1'b0;
  else             dac_dout_seen <= dac_dout;
end
alta_dac dac_inst(
  .enb   (!ctrl_dac_en   ),
  .bufenb(!ctrl_dac_bufen),
  .din   (dac_din        ),
  .stop  (stop           ),
  .dout  (dac_dout       )
);
endmodule
