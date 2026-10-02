module reg_ctrl #(parameter integer REG_GROUPS = 4) (
  input                      clock,
  input                      resetn,
  output [REG_GROUPS*32-1:0] reg_mask,
  output [REG_GROUPS*32-1:0] reg_wren,
  output [REG_GROUPS*32-1:0] reg_wrdata,
  input  [REG_GROUPS*32-1:0] reg_rddata
);

// Define register masks to reduce resource usage. Any mask bit that's defined as 0 will not show up in design and will 
// not be synthesized.
parameter [32*REG_GROUPS-1:0] REG_MASKS = {
  // All mask bits MUST be 32 bits
  32'hffffffff, // reg3
  32'h0000ffff, // reg2
  32'h000000ff, // reg1
  32'h00000001  // reg0
};

genvar i;
generate
for (i = 0; i < REG_GROUPS; i = i + 1) begin : gen_reg
  wire [31:0] wren;
  wire [31:0] wrdata;
  wire [31:0] rddata;

  assign reg_mask[i*32+:32]   = REG_MASKS[i*32+:32];
  assign reg_wren[i*32+:32]   = wren;
  assign reg_wrdata[i*32+:32] = wrdata;
  assign rddata = reg_rddata[i*32+:32];

  // User logic to read/write the registers
  assign wren   = 32'h0;
  assign wrdata = 32'h0;
end
endgenerate

endmodule
