module analog_ip (
  output tri0        LED_D1,
  output tri0        LED_D2,
  output tri0        LED_D3,
  output tri0        LED_D4,
  input              sys_clock,
  input              bus_clock,
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
  output tri0 [31:0] mem_ahb_hrdata,
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
assign mem_ahb_hreadyout = 1'b1;
assign slave_ahb_hready  = 1'b1;

// ---------------------------------------------------------------------------
// Pure-CPLD flowing light: LED_D1..D4 lit one at a time, ~335 ms per step.
// sys_clock = 200 MHz (SYSCLK 200 in cpld_board.ve), resetn from MCU subsystem.
// The MCU is not involved: this counter runs in the CPLD fabric.
// ---------------------------------------------------------------------------
reg [31:0] flow_cnt = 32'd0;
reg [3:0]  flow_pos = 4'b0001;

always @(posedge sys_clock) begin
  if (flow_cnt == 32'd66999999) begin
    flow_cnt <= 32'd0;
    flow_pos <= {flow_pos[2:0], flow_pos[3]};   // rotate one-hot: D1->D2->D3->D4
  end else begin
    flow_cnt <= flow_cnt + 32'd1;
  end
end

// On-board LEDs are ACTIVE-LOW (wired to VCC): drive the lit one LOW.
assign LED_D1 = ~flow_pos[0];
assign LED_D2 = ~flow_pos[1];
assign LED_D3 = ~flow_pos[2];
assign LED_D4 = ~flow_pos[3];

endmodule