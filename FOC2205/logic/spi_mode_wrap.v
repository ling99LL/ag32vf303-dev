// spi_mode_wrap.v — mode-1 SPI bridge for FOC2205 (AG32VF303KCU6 + MT6701 + DRV8316C)
//
// WHY THIS EXISTS: the AG32 hard SPI (SPI0/SPI1) is fixed mode 0 (SCK idle low,
// master samples on the rising edge; no CPOL/CPHA bits exist — see spi.h and
// AgRV2K.svd). MT6701 SSI and DRV8316C SPI both require mode 1: the slave
// launches DO/SDO on the SCK rising edge and samples SDI on the falling edge.
// This bridge re-times the hard SPI's raw function signals into mode-1 timing
// at the pads and captures MISO at the correct instants.
//
// Bridge 0: SPI0 -> DRV8316C (16-clock frames; nSCS shaped here).
// Bridge 1: SPI1 -> MT6701 (24-clock frames; pad CSN is a GPIO pass-through,
//           the hard SPI CSN is used only as an internal frame gate).
//
// TIMING (all margins verified against both datasheets, bus_clock = 100MHz):
//   SCK/MOSI go through a 12-stage pipeline (120ns). MOSI is re-launched on the
//   raw SCK rising edge so it changes right after the delayed SCK rising edge
//   (mode-1 launch) and is stable at the delayed SCK falling edge where the
//   slave samples (setup/hold >= 3 bus clocks at 12.5MHz SCK).
//   MISO is synchronized (2FF) and captured on the delayed SCK falling edge —
//   the true mode-1 sampling instant (TDV 15ns after the rising edge, next
//   change one period away).
//   nSCS (bridge 0) falls as soon as the frame opens and rises 12 bus clocks
//   after the delayed SCK has drained: lead >= 120ns (spec 100/25ns) and
//   trail >= 120ns (spec 0.5*TCLK = 40ns / tHD_nSCS = 25ns).
//
// DATA PATH: MISO shifts into a 32-bit register (MSB first, no shift across
// frames: cleared at frame start). The completed frame is latched at frame end
// and delivered to the MCU over APB at 0x60007000:
//   0x00 SPIW0_RXDATA (RO)  [15:0] = bridge-0 frame, bit15 = first bit
//   0x04 SPIW1_RXDATA (RO)  [23:0] = bridge-1 frame, bit23 = first bit
//   0x08 SPIW_STATUS  (RO)  bit0/1 = frame-done sticky, cleared on RXDATA read
// Firmware: run the hard SPI frame (dummy TX), wait DONE + ~500ns (the latch
// trails the hard SPI DONE by up to ~250ns), then read RXDATA.

`timescale 1ns/1ps

// One mode-1 bridge. f_* are the raw MCU SPI function signals.
module spi_mode1_bridge (
  input             clock,
  input             resetn,
  input             f_sck,        // raw SCK (mode 0, idle low)
  input             f_sck_en,
  input             f_mosi,       // raw MOSI
  input             f_csn,        // raw CSN, active low
  input             f_csn_en,
  input             gate,         // extra frame gate (1 = allow), e.g. GPIO CSN low
  input             miso_i,       // pad MISO (slave DO/SDO)
  output            sck_o,
  output            mosi_o,
  output            csn_o,
  output reg [31:0] rxdata,
  output reg        done_pulse
);
  localparam DEPTH = 12;           // 12 * 10ns = 120ns pipeline

  wire frame   = f_csn_en & ~f_csn & gate;
  wire sck_raw = f_sck & frame;

  reg [DEPTH-1:0] sck_pipe;
  reg [DEPTH-1:0] mosi_pipe;
  reg             mosi_reg;
  reg             sck_raw_d;
  reg [31:0]      rx_shift;
  reg [1:0]       miso_sync;
  reg             sck_o_d;
  reg [4:0]       tail;
  reg             frame_d;

  wire sck_pos   = sck_raw & ~sck_raw_d;
  wire pipe_busy = |sck_pipe;
  wire frame_end = (tail == 5'd1);

  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      sck_pipe  <= {DEPTH{1'b0}};
      mosi_pipe <= {DEPTH{1'b0}};
      mosi_reg  <= 1'b0;
      sck_raw_d <= 1'b0;
    end else begin
      sck_raw_d <= sck_raw;
      sck_pipe  <= {sck_pipe[DEPTH-2:0], sck_raw};
      if (sck_pos) begin
        mosi_reg <= f_mosi;              // mode-1 launch: change on rising edge
      end
      mosi_pipe <= {mosi_pipe[DEPTH-2:0], mosi_reg};
    end
  end

  assign sck_o  = sck_pipe[DEPTH-1];
  assign mosi_o = mosi_pipe[DEPTH-1];

  // MISO: 2FF synchronize, capture on delayed SCK falling edge
  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      miso_sync <= 2'b0;
      sck_o_d   <= 1'b0;
      rx_shift  <= 32'b0;
      frame_d   <= 1'b0;
    end else begin
      miso_sync <= {miso_sync[0], miso_i};
      sck_o_d   <= sck_o;
      frame_d   <= frame;
      if (frame & ~frame_d) begin
        rx_shift <= 32'b0;               // clear at frame start
      end else if (~sck_o & sck_o_d) begin
        rx_shift <= {rx_shift[30:0], miso_sync[1]};
      end
    end
  end

  // Tail: keep CSN low until the pipeline drains + 12 clocks
  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      tail <= 5'd0;
    end else if (frame | pipe_busy) begin
      tail <= 5'd12;
    end else if (tail != 5'd0) begin
      tail <= tail - 5'd1;
    end
  end

  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      rxdata     <= 32'b0;
      done_pulse <= 1'b0;
    end else begin
      done_pulse <= frame_end;
      if (frame_end) begin
        rxdata <= rx_shift;
      end
    end
  end

  // Shaped nSCS: falls with the frame, rises after the tail
  reg csn_r;
  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      csn_r <= 1'b1;
    end else begin
      csn_r <= ~(frame | pipe_busy | (tail != 5'd0));
    end
  end
  assign csn_o = csn_r;

endmodule


module spi_mode_wrap (
  input             clock,
  input             resetn,
  // ---- MCU function wires: SPI0 (bridge 0 -> DRV8316C) ----
  input             spi0_sck_f_out_data,
  input             spi0_sck_f_out_en,
  input             spi0_mosi_f_out_data,
  input             spi0_mosi_f_out_en,
  input             spi0_csn_f_out_data,
  input             spi0_csn_f_out_en,
  // ---- MCU function wires: SPI1 (bridge 1 -> MT6701; CSN = gate only) ----
  input             spi1_sck_f_out_data,
  input             spi1_sck_f_out_en,
  input             spi1_csn_f_out_data,
  input             spi1_csn_f_out_en,
  // ---- MCU function wires: GPIO2_0 = MT6701 CSN ----
  input             spi1_csn_g_out_data,
  input             spi1_csn_g_out_en,
  output            spi1_csn_g_in,
  // ---- pad-facing ----
  output            spi0_sck_o,
  output            spi0_mosi_o,
  output            spi0_csn_o,
  input             spi0_miso_i,
  output            spi1_sck_o,
  input             spi1_miso_i,
  output            spi1_csn_go,
  // ---- APB register bank (one peripheral slot) ----
  input             psel,
  input             penable,
  input             pwrite,
  input  [11:0]     paddr,
  input  [31:0]     pwdata,
  output reg [31:0] prdata
);

  wire [31:0] rxdata0, rxdata1;
  wire        done0, done1;
  reg         done0_sticky, done1_sticky;

  // MT6701 pad CSN: firmware-controlled GPIO pass-through, inactive = high
  assign spi1_csn_go = spi1_csn_g_out_en ? spi1_csn_g_out_data : 1'b1;
  assign spi1_csn_g_in = spi1_csn_go;

  spi_mode1_bridge bridge0 (
    .clock      (clock),
    .resetn     (resetn),
    .f_sck      (spi0_sck_f_out_data),
    .f_sck_en   (spi0_sck_f_out_en),
    .f_mosi     (spi0_mosi_f_out_data),
    .f_csn      (spi0_csn_f_out_data),
    .f_csn_en   (spi0_csn_f_out_en),
    .gate       (1'b1),
    .miso_i     (spi0_miso_i),
    .sck_o      (spi0_sck_o),
    .mosi_o     (spi0_mosi_o),
    .csn_o      (spi0_csn_o),
    .rxdata     (rxdata0),
    .done_pulse (done0)
  );

  spi_mode1_bridge bridge1 (
    .clock      (clock),
    .resetn     (resetn),
    .f_sck      (spi1_sck_f_out_data),
    .f_sck_en   (spi1_sck_f_out_en),
    .f_mosi     (1'b0),                  // SSI is read-only: no MOSI used
    .f_csn      (spi1_csn_f_out_data),
    .f_csn_en   (spi1_csn_f_out_en),
    .gate       (spi1_csn_g_out_en & ~spi1_csn_g_out_data), // SCK only while GPIO CSN low
    .miso_i     (spi1_miso_i),
    .sck_o      (spi1_sck_o),
    .mosi_o     (),                      // unused
    .csn_o      (),                      // unused: pad CSN = spi1_csn_go
    .rxdata     (rxdata1),
    .done_pulse (done1)
  );

  // ---- APB: RO registers ----
  wire rd_strobe = psel & ~pwrite;

  always @ (posedge clock or negedge resetn) begin
    if (!resetn) begin
      done0_sticky <= 1'b0;
      done1_sticky <= 1'b0;
    end else begin
      if (rd_strobe & (paddr[3:2] == 2'd0)) done0_sticky <= 1'b0;
      if (rd_strobe & (paddr[3:2] == 2'd1)) done1_sticky <= 1'b0;
      if (done0) done0_sticky <= 1'b1;
      if (done1) done1_sticky <= 1'b1;
    end
  end

  always @ (*) begin
    case (paddr[3:2])
      2'd0:    prdata = rxdata0;
      2'd1:    prdata = rxdata1;
      2'd2:    prdata = {30'b0, done1_sticky, done0_sticky};
      default: prdata = 32'b0;
    endcase
  end

endmodule
