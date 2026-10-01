`timescale 1 ps/ 1 ps

module cpld_board(
	LED_D1,
	LED_D2,
	LED_D3,
	LED_D4,
	PIN_HSE,
	PIN_HSI,
	PIN_OSC,
	UART0_UARTRXD,
	UART0_UARTTXD);
output	LED_D1;
output	LED_D2;
output	LED_D3;
output	LED_D4;
input	PIN_HSE;
input	PIN_HSI;
input	PIN_OSC;
input	UART0_UARTRXD;
output	UART0_UARTTXD;

//wire	gnd;
//wire	vcc;
//wire	unknown;
wire	AsyncReset_X57_Y1_GND;
wire	AsyncReset_X58_Y1_GND;
wire	AsyncReset_X58_Y2_GND;
wire	AsyncReset_X59_Y1_GND;
wire	AsyncReset_X59_Y2_GND;
wire	\PIN_HSE~input_o ;
wire	\PIN_HSI~input_o ;
wire	\PIN_OSC~input_o ;
wire	\PLL_ENABLE~clkctrl_outclk ;
wire	\PLL_ENABLE~clkctrl_outclk__AsyncReset_X49_Y1_SIG ;
wire	\PLL_ENABLE~combout ;
wire	\PLL_LOCK~combout ;
wire	SyncLoad_X58_Y1_VCC;
wire	SyncReset_X58_Y1_GND;
wire	\UART0_UARTRXD~input_o ;
tri1	devclrn;
tri1	devoe;
tri1	devpor;
wire	\gclksw_inst|clkout ;
wire	\gclksw_inst|clkout_X58_Y1_SIG_VCC ;
wire	\gclksw_inst|clkout_X58_Y2_SIG_VCC ;
wire	\gclksw_inst|clkout_X59_Y1_SIG_VCC ;
wire	\gclksw_inst|clkout_X59_Y2_SIG_VCC ;
wire	\gclksw_inst|clkout__macro_inst|Equal0~10_Duplicate_12_X57_Y1_SIG_SIG ;
wire	\gclksw_inst|clkout__macro_inst|Equal0~10_combout_X58_Y1_SIG_SIG ;
wire	\gclksw_inst|gclk_switch__alta_gclksw__clkout ;
wire	[7:0] gpio7_io_out_data;
//wire	gpio7_io_out_data[0];
//wire	gpio7_io_out_data[1];
//wire	gpio7_io_out_data[2];
//wire	gpio7_io_out_data[3];
//wire	gpio7_io_out_data[4];
//wire	gpio7_io_out_data[5];
//wire	gpio7_io_out_data[6];
//wire	gpio7_io_out_data[7];
wire	[7:0] gpio7_io_out_en;
//wire	gpio7_io_out_en[0];
//wire	gpio7_io_out_en[1];
//wire	gpio7_io_out_en[2];
//wire	gpio7_io_out_en[3];
//wire	gpio7_io_out_en[4];
//wire	gpio7_io_out_en[5];
//wire	gpio7_io_out_en[6];
//wire	gpio7_io_out_en[7];
wire	\macro_inst|Add0~0_combout ;
wire	\macro_inst|Add0~1 ;
wire	\macro_inst|Add0~10_combout ;
wire	\macro_inst|Add0~11 ;
wire	\macro_inst|Add0~12_combout ;
wire	\macro_inst|Add0~13 ;
wire	\macro_inst|Add0~14_combout ;
wire	\macro_inst|Add0~15 ;
wire	\macro_inst|Add0~16_combout ;
wire	\macro_inst|Add0~17 ;
wire	\macro_inst|Add0~18_combout ;
wire	\macro_inst|Add0~19 ;
wire	\macro_inst|Add0~20_combout ;
wire	\macro_inst|Add0~21 ;
wire	\macro_inst|Add0~22_combout ;
wire	\macro_inst|Add0~23 ;
wire	\macro_inst|Add0~24_combout ;
wire	\macro_inst|Add0~25 ;
wire	\macro_inst|Add0~26_combout ;
wire	\macro_inst|Add0~27 ;
wire	\macro_inst|Add0~28_combout ;
wire	\macro_inst|Add0~29 ;
wire	\macro_inst|Add0~2_combout ;
wire	\macro_inst|Add0~3 ;
wire	\macro_inst|Add0~30_combout ;
wire	\macro_inst|Add0~31 ;
wire	\macro_inst|Add0~32_combout ;
wire	\macro_inst|Add0~33 ;
wire	\macro_inst|Add0~34_combout ;
wire	\macro_inst|Add0~35 ;
wire	\macro_inst|Add0~36_combout ;
wire	\macro_inst|Add0~37 ;
wire	\macro_inst|Add0~38_combout ;
wire	\macro_inst|Add0~39 ;
wire	\macro_inst|Add0~40_combout ;
wire	\macro_inst|Add0~41 ;
wire	\macro_inst|Add0~42_combout ;
wire	\macro_inst|Add0~43 ;
wire	\macro_inst|Add0~44_combout ;
wire	\macro_inst|Add0~45 ;
wire	\macro_inst|Add0~46_combout ;
wire	\macro_inst|Add0~47 ;
wire	\macro_inst|Add0~48_combout ;
wire	\macro_inst|Add0~49 ;
wire	\macro_inst|Add0~4_combout ;
wire	\macro_inst|Add0~5 ;
wire	\macro_inst|Add0~50_combout ;
wire	\macro_inst|Add0~51 ;
wire	\macro_inst|Add0~52_combout ;
wire	\macro_inst|Add0~53 ;
wire	\macro_inst|Add0~54_combout ;
wire	\macro_inst|Add0~55 ;
wire	\macro_inst|Add0~56_combout ;
wire	\macro_inst|Add0~57 ;
wire	\macro_inst|Add0~58_combout ;
wire	\macro_inst|Add0~59 ;
wire	\macro_inst|Add0~60_combout ;
wire	\macro_inst|Add0~61 ;
wire	\macro_inst|Add0~62_combout ;
wire	\macro_inst|Add0~6_combout ;
wire	\macro_inst|Add0~7 ;
wire	\macro_inst|Add0~8_combout ;
wire	\macro_inst|Add0~9 ;
wire	\macro_inst|Equal0~0_combout ;
wire	\macro_inst|Equal0~10_Duplicate_12 ;
wire	\macro_inst|Equal0~10_combout ;
wire	\macro_inst|Equal0~1_combout ;
wire	\macro_inst|Equal0~2_combout ;
wire	\macro_inst|Equal0~3_combout ;
wire	\macro_inst|Equal0~4_combout ;
wire	\macro_inst|Equal0~5_combout ;
wire	\macro_inst|Equal0~6_combout ;
wire	\macro_inst|Equal0~7_combout ;
wire	\macro_inst|Equal0~8_combout ;
wire	\macro_inst|Equal0~9_combout ;
wire	[31:0] \macro_inst|flow_cnt ;
//wire	\macro_inst|flow_cnt [0];
//wire	\macro_inst|flow_cnt [10];
//wire	\macro_inst|flow_cnt [11];
//wire	\macro_inst|flow_cnt [12];
//wire	\macro_inst|flow_cnt [13];
//wire	\macro_inst|flow_cnt [14];
//wire	\macro_inst|flow_cnt [15];
//wire	\macro_inst|flow_cnt [16];
//wire	\macro_inst|flow_cnt [17];
//wire	\macro_inst|flow_cnt [18];
//wire	\macro_inst|flow_cnt [19];
//wire	\macro_inst|flow_cnt [1];
//wire	\macro_inst|flow_cnt [20];
//wire	\macro_inst|flow_cnt [21];
//wire	\macro_inst|flow_cnt [22];
//wire	\macro_inst|flow_cnt [23];
//wire	\macro_inst|flow_cnt [24];
//wire	\macro_inst|flow_cnt [25];
//wire	\macro_inst|flow_cnt [26];
//wire	\macro_inst|flow_cnt [27];
//wire	\macro_inst|flow_cnt [28];
//wire	\macro_inst|flow_cnt [29];
//wire	\macro_inst|flow_cnt [2];
//wire	\macro_inst|flow_cnt [30];
//wire	\macro_inst|flow_cnt [31];
//wire	\macro_inst|flow_cnt [3];
//wire	\macro_inst|flow_cnt [4];
//wire	\macro_inst|flow_cnt [5];
//wire	\macro_inst|flow_cnt [6];
//wire	\macro_inst|flow_cnt [7];
//wire	\macro_inst|flow_cnt [8];
//wire	\macro_inst|flow_cnt [9];
wire	\macro_inst|flow_cnt~0_combout ;
wire	\macro_inst|flow_cnt~10_combout ;
wire	\macro_inst|flow_cnt~11_combout ;
wire	\macro_inst|flow_cnt~12_combout ;
wire	\macro_inst|flow_cnt~13_combout ;
wire	\macro_inst|flow_cnt~14_combout ;
wire	\macro_inst|flow_cnt~1_combout ;
wire	\macro_inst|flow_cnt~2_combout ;
wire	\macro_inst|flow_cnt~3_combout ;
wire	\macro_inst|flow_cnt~4_combout ;
wire	\macro_inst|flow_cnt~5_combout ;
wire	\macro_inst|flow_cnt~6_combout ;
wire	\macro_inst|flow_cnt~7_combout ;
wire	\macro_inst|flow_cnt~8_combout ;
wire	\macro_inst|flow_cnt~9_combout ;
wire	[3:0] \macro_inst|flow_pos ;
//wire	\macro_inst|flow_pos [0];
wire	\macro_inst|flow_pos[0]~0_combout ;
//wire	\macro_inst|flow_pos [1];
wire	\macro_inst|flow_pos[1]~1_combout ;
wire	\macro_inst|flow_pos[1]~feeder_combout ;
//wire	\macro_inst|flow_pos [2];
//wire	\macro_inst|flow_pos [3];
wire	\macro_inst|flow_pos[3]~feeder_combout ;
wire	[4:0] \pll_inst|auto_generated|clk ;
//wire	\pll_inst|auto_generated|clk [0];
//wire	\pll_inst|auto_generated|clk [1];
//wire	\pll_inst|auto_generated|clk [2];
//wire	\pll_inst|auto_generated|clk [3];
//wire	\pll_inst|auto_generated|clk [4];
wire	[4:0] \pll_inst|auto_generated|pll1_CLK_bus ;
//wire	\pll_inst|auto_generated|pll1_CLK_bus [0];
//wire	\pll_inst|auto_generated|pll1_CLK_bus [1];
//wire	\pll_inst|auto_generated|pll1_CLK_bus [2];
//wire	\pll_inst|auto_generated|pll1_CLK_bus [3];
//wire	\pll_inst|auto_generated|pll1_CLK_bus [4];
wire	\pll_inst|auto_generated|pll1~FBOUT ;
wire	\pll_inst|auto_generated|pll1~LOCKED ;
wire	\pll_inst|auto_generated|pll1~LOCKED_X49_Y1_SIG_VCC ;
wire	\pll_inst|auto_generated|pll_lock_sync~feeder_combout ;
wire	\pll_inst|auto_generated|pll_lock_sync~q ;
wire	[1:0] sys_ctrl_clkSource;
//wire	sys_ctrl_clkSource[0];
//wire	sys_ctrl_clkSource[1];

wire vcc;
wire gnd;
assign vcc = 1'b1;
assign gnd = 1'b0;
wire unknown;
assign unknown = 1'bx;

alta_rio \LED_D1~output (
	.padio(LED_D1),
	.datain(\macro_inst|flow_pos [0]),
	.oe(vcc),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(),
	.regout());
defparam \LED_D1~output .coord_x = 18;
defparam \LED_D1~output .coord_y = 13;
defparam \LED_D1~output .coord_z = 1;
defparam \LED_D1~output .IN_ASYNC_MODE = 1'b0;
defparam \LED_D1~output .IN_SYNC_MODE = 1'b0;
defparam \LED_D1~output .IN_POWERUP = 1'b0;
defparam \LED_D1~output .OUT_REG_MODE = 1'b0;
defparam \LED_D1~output .OUT_ASYNC_MODE = 1'b0;
defparam \LED_D1~output .OUT_SYNC_MODE = 1'b0;
defparam \LED_D1~output .OUT_POWERUP = 1'b0;
defparam \LED_D1~output .OE_REG_MODE = 1'b0;
defparam \LED_D1~output .OE_ASYNC_MODE = 1'b0;
defparam \LED_D1~output .OE_SYNC_MODE = 1'b0;
defparam \LED_D1~output .OE_POWERUP = 1'b0;
defparam \LED_D1~output .CFG_TRI_INPUT = 1'b0;
defparam \LED_D1~output .CFG_INPUT_EN = 1'b0;
defparam \LED_D1~output .CFG_PULL_UP = 1'b0;
defparam \LED_D1~output .CFG_SLR = 1'b0;
defparam \LED_D1~output .CFG_OPEN_DRAIN = 1'b0;
defparam \LED_D1~output .CFG_PDRCTRL = 4'b0100;
defparam \LED_D1~output .CFG_KEEP = 2'b00;
defparam \LED_D1~output .CFG_LVDS_OUT_EN = 1'b0;
defparam \LED_D1~output .CFG_LVDS_SEL_CUA = 2'b00;
defparam \LED_D1~output .CFG_LVDS_IREF = 10'b0110000000;
defparam \LED_D1~output .CFG_LVDS_IN_EN = 1'b0;
defparam \LED_D1~output .DPCLK_DELAY = 4'b0000;
defparam \LED_D1~output .OUT_DELAY = 1'b0;
defparam \LED_D1~output .IN_DATA_DELAY = 3'b000;
defparam \LED_D1~output .IN_REG_DELAY = 3'b000;

alta_rio \LED_D2~output (
	.padio(LED_D2),
	.datain(!\macro_inst|flow_pos [1]),
	.oe(vcc),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(),
	.regout());
defparam \LED_D2~output .coord_x = 18;
defparam \LED_D2~output .coord_y = 13;
defparam \LED_D2~output .coord_z = 2;
defparam \LED_D2~output .IN_ASYNC_MODE = 1'b0;
defparam \LED_D2~output .IN_SYNC_MODE = 1'b0;
defparam \LED_D2~output .IN_POWERUP = 1'b0;
defparam \LED_D2~output .OUT_REG_MODE = 1'b0;
defparam \LED_D2~output .OUT_ASYNC_MODE = 1'b0;
defparam \LED_D2~output .OUT_SYNC_MODE = 1'b0;
defparam \LED_D2~output .OUT_POWERUP = 1'b0;
defparam \LED_D2~output .OE_REG_MODE = 1'b0;
defparam \LED_D2~output .OE_ASYNC_MODE = 1'b0;
defparam \LED_D2~output .OE_SYNC_MODE = 1'b0;
defparam \LED_D2~output .OE_POWERUP = 1'b0;
defparam \LED_D2~output .CFG_TRI_INPUT = 1'b0;
defparam \LED_D2~output .CFG_INPUT_EN = 1'b0;
defparam \LED_D2~output .CFG_PULL_UP = 1'b0;
defparam \LED_D2~output .CFG_SLR = 1'b0;
defparam \LED_D2~output .CFG_OPEN_DRAIN = 1'b0;
defparam \LED_D2~output .CFG_PDRCTRL = 4'b0100;
defparam \LED_D2~output .CFG_KEEP = 2'b00;
defparam \LED_D2~output .CFG_LVDS_OUT_EN = 1'b0;
defparam \LED_D2~output .CFG_LVDS_SEL_CUA = 2'b00;
defparam \LED_D2~output .CFG_LVDS_IREF = 10'b0110000000;
defparam \LED_D2~output .CFG_LVDS_IN_EN = 1'b0;
defparam \LED_D2~output .DPCLK_DELAY = 4'b0000;
defparam \LED_D2~output .OUT_DELAY = 1'b0;
defparam \LED_D2~output .IN_DATA_DELAY = 3'b000;
defparam \LED_D2~output .IN_REG_DELAY = 3'b000;

alta_rio \LED_D3~output (
	.padio(LED_D3),
	.datain(!\macro_inst|flow_pos [2]),
	.oe(vcc),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(),
	.regout());
defparam \LED_D3~output .coord_x = 18;
defparam \LED_D3~output .coord_y = 13;
defparam \LED_D3~output .coord_z = 3;
defparam \LED_D3~output .IN_ASYNC_MODE = 1'b0;
defparam \LED_D3~output .IN_SYNC_MODE = 1'b0;
defparam \LED_D3~output .IN_POWERUP = 1'b0;
defparam \LED_D3~output .OUT_REG_MODE = 1'b0;
defparam \LED_D3~output .OUT_ASYNC_MODE = 1'b0;
defparam \LED_D3~output .OUT_SYNC_MODE = 1'b0;
defparam \LED_D3~output .OUT_POWERUP = 1'b0;
defparam \LED_D3~output .OE_REG_MODE = 1'b0;
defparam \LED_D3~output .OE_ASYNC_MODE = 1'b0;
defparam \LED_D3~output .OE_SYNC_MODE = 1'b0;
defparam \LED_D3~output .OE_POWERUP = 1'b0;
defparam \LED_D3~output .CFG_TRI_INPUT = 1'b0;
defparam \LED_D3~output .CFG_INPUT_EN = 1'b0;
defparam \LED_D3~output .CFG_PULL_UP = 1'b0;
defparam \LED_D3~output .CFG_SLR = 1'b0;
defparam \LED_D3~output .CFG_OPEN_DRAIN = 1'b0;
defparam \LED_D3~output .CFG_PDRCTRL = 4'b0100;
defparam \LED_D3~output .CFG_KEEP = 2'b00;
defparam \LED_D3~output .CFG_LVDS_OUT_EN = 1'b0;
defparam \LED_D3~output .CFG_LVDS_SEL_CUA = 2'b00;
defparam \LED_D3~output .CFG_LVDS_IREF = 10'b0110000000;
defparam \LED_D3~output .CFG_LVDS_IN_EN = 1'b0;
defparam \LED_D3~output .DPCLK_DELAY = 4'b0000;
defparam \LED_D3~output .OUT_DELAY = 1'b0;
defparam \LED_D3~output .IN_DATA_DELAY = 3'b000;
defparam \LED_D3~output .IN_REG_DELAY = 3'b000;

alta_rio \LED_D4~output (
	.padio(LED_D4),
	.datain(!\macro_inst|flow_pos [3]),
	.oe(vcc),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(),
	.regout());
defparam \LED_D4~output .coord_x = 19;
defparam \LED_D4~output .coord_y = 13;
defparam \LED_D4~output .coord_z = 0;
defparam \LED_D4~output .IN_ASYNC_MODE = 1'b0;
defparam \LED_D4~output .IN_SYNC_MODE = 1'b0;
defparam \LED_D4~output .IN_POWERUP = 1'b0;
defparam \LED_D4~output .OUT_REG_MODE = 1'b0;
defparam \LED_D4~output .OUT_ASYNC_MODE = 1'b0;
defparam \LED_D4~output .OUT_SYNC_MODE = 1'b0;
defparam \LED_D4~output .OUT_POWERUP = 1'b0;
defparam \LED_D4~output .OE_REG_MODE = 1'b0;
defparam \LED_D4~output .OE_ASYNC_MODE = 1'b0;
defparam \LED_D4~output .OE_SYNC_MODE = 1'b0;
defparam \LED_D4~output .OE_POWERUP = 1'b0;
defparam \LED_D4~output .CFG_TRI_INPUT = 1'b0;
defparam \LED_D4~output .CFG_INPUT_EN = 1'b0;
defparam \LED_D4~output .CFG_PULL_UP = 1'b0;
defparam \LED_D4~output .CFG_SLR = 1'b0;
defparam \LED_D4~output .CFG_OPEN_DRAIN = 1'b0;
defparam \LED_D4~output .CFG_PDRCTRL = 4'b0100;
defparam \LED_D4~output .CFG_KEEP = 2'b00;
defparam \LED_D4~output .CFG_LVDS_OUT_EN = 1'b0;
defparam \LED_D4~output .CFG_LVDS_SEL_CUA = 2'b00;
defparam \LED_D4~output .CFG_LVDS_IREF = 10'b0110000000;
defparam \LED_D4~output .CFG_LVDS_IN_EN = 1'b0;
defparam \LED_D4~output .DPCLK_DELAY = 4'b0000;
defparam \LED_D4~output .OUT_DELAY = 1'b0;
defparam \LED_D4~output .IN_DATA_DELAY = 3'b000;
defparam \LED_D4~output .IN_REG_DELAY = 3'b000;

alta_rio \PIN_HSE~input (
	.padio(PIN_HSE),
	.datain(gnd),
	.oe(gnd),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(\PIN_HSE~input_o ),
	.regout());
defparam \PIN_HSE~input .coord_x = 22;
defparam \PIN_HSE~input .coord_y = 4;
defparam \PIN_HSE~input .coord_z = 1;
defparam \PIN_HSE~input .IN_ASYNC_MODE = 1'b0;
defparam \PIN_HSE~input .IN_SYNC_MODE = 1'b0;
defparam \PIN_HSE~input .IN_POWERUP = 1'b0;
defparam \PIN_HSE~input .OUT_REG_MODE = 1'b0;
defparam \PIN_HSE~input .OUT_ASYNC_MODE = 1'b0;
defparam \PIN_HSE~input .OUT_SYNC_MODE = 1'b0;
defparam \PIN_HSE~input .OUT_POWERUP = 1'b0;
defparam \PIN_HSE~input .OE_REG_MODE = 1'b0;
defparam \PIN_HSE~input .OE_ASYNC_MODE = 1'b0;
defparam \PIN_HSE~input .OE_SYNC_MODE = 1'b0;
defparam \PIN_HSE~input .OE_POWERUP = 1'b0;
defparam \PIN_HSE~input .CFG_TRI_INPUT = 1'b0;
defparam \PIN_HSE~input .CFG_PULL_UP = 1'b0;
defparam \PIN_HSE~input .CFG_SLR = 1'b0;
defparam \PIN_HSE~input .CFG_OPEN_DRAIN = 1'b0;
defparam \PIN_HSE~input .CFG_PDRCTRL = 4'b0010;
defparam \PIN_HSE~input .CFG_KEEP = 2'b00;
defparam \PIN_HSE~input .CFG_LVDS_OUT_EN = 1'b0;
defparam \PIN_HSE~input .CFG_LVDS_SEL_CUA = 2'b00;
defparam \PIN_HSE~input .CFG_LVDS_IREF = 10'b0110000000;
defparam \PIN_HSE~input .CFG_LVDS_IN_EN = 1'b0;
defparam \PIN_HSE~input .DPCLK_DELAY = 4'b0000;
defparam \PIN_HSE~input .OUT_DELAY = 1'b0;
defparam \PIN_HSE~input .IN_DATA_DELAY = 3'b000;
defparam \PIN_HSE~input .IN_REG_DELAY = 3'b000;

alta_rio \PIN_HSI~input (
	.padio(PIN_HSI),
	.datain(gnd),
	.oe(gnd),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(\PIN_HSI~input_o ),
	.regout());
defparam \PIN_HSI~input .coord_x = 22;
defparam \PIN_HSI~input .coord_y = 4;
defparam \PIN_HSI~input .coord_z = 0;
defparam \PIN_HSI~input .IN_ASYNC_MODE = 1'b0;
defparam \PIN_HSI~input .IN_SYNC_MODE = 1'b0;
defparam \PIN_HSI~input .IN_POWERUP = 1'b0;
defparam \PIN_HSI~input .OUT_REG_MODE = 1'b0;
defparam \PIN_HSI~input .OUT_ASYNC_MODE = 1'b0;
defparam \PIN_HSI~input .OUT_SYNC_MODE = 1'b0;
defparam \PIN_HSI~input .OUT_POWERUP = 1'b0;
defparam \PIN_HSI~input .OE_REG_MODE = 1'b0;
defparam \PIN_HSI~input .OE_ASYNC_MODE = 1'b0;
defparam \PIN_HSI~input .OE_SYNC_MODE = 1'b0;
defparam \PIN_HSI~input .OE_POWERUP = 1'b0;
defparam \PIN_HSI~input .CFG_TRI_INPUT = 1'b0;
defparam \PIN_HSI~input .CFG_PULL_UP = 1'b0;
defparam \PIN_HSI~input .CFG_SLR = 1'b0;
defparam \PIN_HSI~input .CFG_OPEN_DRAIN = 1'b0;
defparam \PIN_HSI~input .CFG_PDRCTRL = 4'b0010;
defparam \PIN_HSI~input .CFG_KEEP = 2'b00;
defparam \PIN_HSI~input .CFG_LVDS_OUT_EN = 1'b0;
defparam \PIN_HSI~input .CFG_LVDS_SEL_CUA = 2'b00;
defparam \PIN_HSI~input .CFG_LVDS_IREF = 10'b0110000000;
defparam \PIN_HSI~input .CFG_LVDS_IN_EN = 1'b0;
defparam \PIN_HSI~input .DPCLK_DELAY = 4'b0000;
defparam \PIN_HSI~input .OUT_DELAY = 1'b0;
defparam \PIN_HSI~input .IN_DATA_DELAY = 3'b000;
defparam \PIN_HSI~input .IN_REG_DELAY = 3'b000;

alta_rio \PIN_OSC~input (
	.padio(PIN_OSC),
	.datain(gnd),
	.oe(gnd),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(\PIN_OSC~input_o ),
	.regout());
defparam \PIN_OSC~input .coord_x = 22;
defparam \PIN_OSC~input .coord_y = 4;
defparam \PIN_OSC~input .coord_z = 2;
defparam \PIN_OSC~input .IN_ASYNC_MODE = 1'b0;
defparam \PIN_OSC~input .IN_SYNC_MODE = 1'b0;
defparam \PIN_OSC~input .IN_POWERUP = 1'b0;
defparam \PIN_OSC~input .OUT_REG_MODE = 1'b0;
defparam \PIN_OSC~input .OUT_ASYNC_MODE = 1'b0;
defparam \PIN_OSC~input .OUT_SYNC_MODE = 1'b0;
defparam \PIN_OSC~input .OUT_POWERUP = 1'b0;
defparam \PIN_OSC~input .OE_REG_MODE = 1'b0;
defparam \PIN_OSC~input .OE_ASYNC_MODE = 1'b0;
defparam \PIN_OSC~input .OE_SYNC_MODE = 1'b0;
defparam \PIN_OSC~input .OE_POWERUP = 1'b0;
defparam \PIN_OSC~input .CFG_TRI_INPUT = 1'b0;
defparam \PIN_OSC~input .CFG_PULL_UP = 1'b0;
defparam \PIN_OSC~input .CFG_SLR = 1'b0;
defparam \PIN_OSC~input .CFG_OPEN_DRAIN = 1'b0;
defparam \PIN_OSC~input .CFG_PDRCTRL = 4'b0010;
defparam \PIN_OSC~input .CFG_KEEP = 2'b00;
defparam \PIN_OSC~input .CFG_LVDS_OUT_EN = 1'b0;
defparam \PIN_OSC~input .CFG_LVDS_SEL_CUA = 2'b00;
defparam \PIN_OSC~input .CFG_LVDS_IREF = 10'b0110000000;
defparam \PIN_OSC~input .CFG_LVDS_IN_EN = 1'b0;
defparam \PIN_OSC~input .DPCLK_DELAY = 4'b0000;
defparam \PIN_OSC~input .OUT_DELAY = 1'b0;
defparam \PIN_OSC~input .IN_DATA_DELAY = 3'b000;
defparam \PIN_OSC~input .IN_REG_DELAY = 3'b000;

alta_slice PLL_ENABLE(
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(\PLL_LOCK~combout ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\PLL_ENABLE~combout ),
	.Cout(),
	.Q());
defparam PLL_ENABLE.coord_x = 19;
defparam PLL_ENABLE.coord_y = 4;
defparam PLL_ENABLE.coord_z = 14;
defparam PLL_ENABLE.mask = 16'h00FF;
defparam PLL_ENABLE.modeMux = 1'b0;
defparam PLL_ENABLE.FeedbackMux = 1'b0;
defparam PLL_ENABLE.ShiftMux = 1'b0;
defparam PLL_ENABLE.BypassEn = 1'b0;
defparam PLL_ENABLE.CarryEnb = 1'b1;

alta_io_gclk \PLL_ENABLE~clkctrl (
	.inclk(\PLL_ENABLE~combout ),
	.outclk(\PLL_ENABLE~clkctrl_outclk ));
defparam \PLL_ENABLE~clkctrl .coord_x = 22;
defparam \PLL_ENABLE~clkctrl .coord_y = 4;
defparam \PLL_ENABLE~clkctrl .coord_z = 4;

alta_slice PLL_LOCK(
	.A(vcc),
	.B(\pll_inst|auto_generated|pll_lock_sync~q ),
	.C(vcc),
	.D(\pll_inst|auto_generated|pll1~LOCKED ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\PLL_LOCK~combout ),
	.Cout(),
	.Q());
defparam PLL_LOCK.coord_x = 19;
defparam PLL_LOCK.coord_y = 4;
defparam PLL_LOCK.coord_z = 13;
defparam PLL_LOCK.mask = 16'hCC00;
defparam PLL_LOCK.modeMux = 1'b0;
defparam PLL_LOCK.FeedbackMux = 1'b0;
defparam PLL_LOCK.ShiftMux = 1'b0;
defparam PLL_LOCK.BypassEn = 1'b0;
defparam PLL_LOCK.CarryEnb = 1'b1;

alta_rio \UART0_UARTRXD~input (
	.padio(UART0_UARTRXD),
	.datain(gnd),
	.oe(gnd),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(\UART0_UARTRXD~input_o ),
	.regout());
defparam \UART0_UARTRXD~input .coord_x = 0;
defparam \UART0_UARTRXD~input .coord_y = 1;
defparam \UART0_UARTRXD~input .coord_z = 0;
defparam \UART0_UARTRXD~input .IN_ASYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .IN_SYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .IN_POWERUP = 1'b0;
defparam \UART0_UARTRXD~input .OUT_REG_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OUT_ASYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OUT_SYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OUT_POWERUP = 1'b0;
defparam \UART0_UARTRXD~input .OE_REG_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OE_ASYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OE_SYNC_MODE = 1'b0;
defparam \UART0_UARTRXD~input .OE_POWERUP = 1'b0;
defparam \UART0_UARTRXD~input .CFG_TRI_INPUT = 1'b0;
defparam \UART0_UARTRXD~input .CFG_INPUT_EN = 1'b0;
defparam \UART0_UARTRXD~input .CFG_PULL_UP = 1'b0;
defparam \UART0_UARTRXD~input .CFG_SLR = 1'b0;
defparam \UART0_UARTRXD~input .CFG_OPEN_DRAIN = 1'b0;
defparam \UART0_UARTRXD~input .CFG_PDRCTRL = 4'b0100;
defparam \UART0_UARTRXD~input .CFG_KEEP = 2'b00;
defparam \UART0_UARTRXD~input .CFG_LVDS_OUT_EN = 1'b0;
defparam \UART0_UARTRXD~input .CFG_LVDS_SEL_CUA = 2'b00;
defparam \UART0_UARTRXD~input .CFG_LVDS_IREF = 10'b0110000000;
defparam \UART0_UARTRXD~input .CFG_LVDS_IN_EN = 1'b0;
defparam \UART0_UARTRXD~input .DPCLK_DELAY = 4'b0000;
defparam \UART0_UARTRXD~input .OUT_DELAY = 1'b0;
defparam \UART0_UARTRXD~input .IN_DATA_DELAY = 3'b000;
defparam \UART0_UARTRXD~input .IN_REG_DELAY = 3'b000;

alta_rio \UART0_UARTTXD~output (
	.padio(UART0_UARTTXD),
	.datain(gnd),
	.oe(gnd),
	.outclk(gnd),
	.outclkena(vcc),
	.inclk(gnd),
	.inclkena(vcc),
	.areset(gnd),
	.sreset(gnd),
	.combout(),
	.regout());
defparam \UART0_UARTTXD~output .coord_x = 0;
defparam \UART0_UARTTXD~output .coord_y = 2;
defparam \UART0_UARTTXD~output .coord_z = 5;
defparam \UART0_UARTTXD~output .IN_ASYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .IN_SYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .IN_POWERUP = 1'b0;
defparam \UART0_UARTTXD~output .OUT_REG_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OUT_ASYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OUT_SYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OUT_POWERUP = 1'b0;
defparam \UART0_UARTTXD~output .OE_REG_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OE_ASYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OE_SYNC_MODE = 1'b0;
defparam \UART0_UARTTXD~output .OE_POWERUP = 1'b0;
defparam \UART0_UARTTXD~output .CFG_TRI_INPUT = 1'b0;
defparam \UART0_UARTTXD~output .CFG_INPUT_EN = 1'b0;
defparam \UART0_UARTTXD~output .CFG_PULL_UP = 1'b0;
defparam \UART0_UARTTXD~output .CFG_SLR = 1'b0;
defparam \UART0_UARTTXD~output .CFG_OPEN_DRAIN = 1'b0;
defparam \UART0_UARTTXD~output .CFG_PDRCTRL = 4'b0100;
defparam \UART0_UARTTXD~output .CFG_KEEP = 2'b00;
defparam \UART0_UARTTXD~output .CFG_LVDS_OUT_EN = 1'b0;
defparam \UART0_UARTTXD~output .CFG_LVDS_SEL_CUA = 2'b00;
defparam \UART0_UARTTXD~output .CFG_LVDS_IREF = 10'b0110000000;
defparam \UART0_UARTTXD~output .CFG_LVDS_IN_EN = 1'b0;
defparam \UART0_UARTTXD~output .DPCLK_DELAY = 4'b0000;
defparam \UART0_UARTTXD~output .OUT_DELAY = 1'b0;
defparam \UART0_UARTTXD~output .IN_DATA_DELAY = 3'b000;
defparam \UART0_UARTTXD~output .IN_REG_DELAY = 3'b000;

alta_asyncctrl asyncreset_ctrl_X49_Y1_N0(
	.Din(\PLL_ENABLE~clkctrl_outclk ),
	.Dout(\PLL_ENABLE~clkctrl_outclk__AsyncReset_X49_Y1_SIG ));
defparam asyncreset_ctrl_X49_Y1_N0.coord_x = 19;
defparam asyncreset_ctrl_X49_Y1_N0.coord_y = 4;
defparam asyncreset_ctrl_X49_Y1_N0.coord_z = 0;
defparam asyncreset_ctrl_X49_Y1_N0.AsyncCtrlMux = 2'b10;

alta_asyncctrl asyncreset_ctrl_X57_Y1_N0(
	.Din(),
	.Dout(AsyncReset_X57_Y1_GND));
defparam asyncreset_ctrl_X57_Y1_N0.coord_x = 19;
defparam asyncreset_ctrl_X57_Y1_N0.coord_y = 9;
defparam asyncreset_ctrl_X57_Y1_N0.coord_z = 0;
defparam asyncreset_ctrl_X57_Y1_N0.AsyncCtrlMux = 2'b00;

alta_asyncctrl asyncreset_ctrl_X58_Y1_N0(
	.Din(),
	.Dout(AsyncReset_X58_Y1_GND));
defparam asyncreset_ctrl_X58_Y1_N0.coord_x = 18;
defparam asyncreset_ctrl_X58_Y1_N0.coord_y = 9;
defparam asyncreset_ctrl_X58_Y1_N0.coord_z = 0;
defparam asyncreset_ctrl_X58_Y1_N0.AsyncCtrlMux = 2'b00;

alta_asyncctrl asyncreset_ctrl_X58_Y2_N0(
	.Din(),
	.Dout(AsyncReset_X58_Y2_GND));
defparam asyncreset_ctrl_X58_Y2_N0.coord_x = 18;
defparam asyncreset_ctrl_X58_Y2_N0.coord_y = 10;
defparam asyncreset_ctrl_X58_Y2_N0.coord_z = 0;
defparam asyncreset_ctrl_X58_Y2_N0.AsyncCtrlMux = 2'b00;

alta_asyncctrl asyncreset_ctrl_X59_Y1_N0(
	.Din(),
	.Dout(AsyncReset_X59_Y1_GND));
defparam asyncreset_ctrl_X59_Y1_N0.coord_x = 17;
defparam asyncreset_ctrl_X59_Y1_N0.coord_y = 9;
defparam asyncreset_ctrl_X59_Y1_N0.coord_z = 0;
defparam asyncreset_ctrl_X59_Y1_N0.AsyncCtrlMux = 2'b00;

alta_asyncctrl asyncreset_ctrl_X59_Y2_N0(
	.Din(),
	.Dout(AsyncReset_X59_Y2_GND));
defparam asyncreset_ctrl_X59_Y2_N0.coord_x = 17;
defparam asyncreset_ctrl_X59_Y2_N0.coord_y = 10;
defparam asyncreset_ctrl_X59_Y2_N0.coord_z = 0;
defparam asyncreset_ctrl_X59_Y2_N0.AsyncCtrlMux = 2'b00;

alta_clkenctrl clken_ctrl_X49_Y1_N0(
	.ClkIn(\pll_inst|auto_generated|pll1~LOCKED ),
	.ClkEn(),
	.ClkOut(\pll_inst|auto_generated|pll1~LOCKED_X49_Y1_SIG_VCC ));
defparam clken_ctrl_X49_Y1_N0.coord_x = 19;
defparam clken_ctrl_X49_Y1_N0.coord_y = 4;
defparam clken_ctrl_X49_Y1_N0.coord_z = 0;
defparam clken_ctrl_X49_Y1_N0.ClkMux = 2'b10;
defparam clken_ctrl_X49_Y1_N0.ClkEnMux = 2'b01;

alta_clkenctrl clken_ctrl_X57_Y1_N0(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(\macro_inst|Equal0~10_Duplicate_12 ),
	.ClkOut(\gclksw_inst|clkout__macro_inst|Equal0~10_Duplicate_12_X57_Y1_SIG_SIG ));
defparam clken_ctrl_X57_Y1_N0.coord_x = 19;
defparam clken_ctrl_X57_Y1_N0.coord_y = 9;
defparam clken_ctrl_X57_Y1_N0.coord_z = 0;
defparam clken_ctrl_X57_Y1_N0.ClkMux = 2'b10;
defparam clken_ctrl_X57_Y1_N0.ClkEnMux = 2'b10;

alta_clkenctrl clken_ctrl_X58_Y1_N0(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(),
	.ClkOut(\gclksw_inst|clkout_X58_Y1_SIG_VCC ));
defparam clken_ctrl_X58_Y1_N0.coord_x = 18;
defparam clken_ctrl_X58_Y1_N0.coord_y = 9;
defparam clken_ctrl_X58_Y1_N0.coord_z = 0;
defparam clken_ctrl_X58_Y1_N0.ClkMux = 2'b10;
defparam clken_ctrl_X58_Y1_N0.ClkEnMux = 2'b01;

alta_clkenctrl clken_ctrl_X58_Y1_N1(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(\macro_inst|Equal0~10_combout ),
	.ClkOut(\gclksw_inst|clkout__macro_inst|Equal0~10_combout_X58_Y1_SIG_SIG ));
defparam clken_ctrl_X58_Y1_N1.coord_x = 18;
defparam clken_ctrl_X58_Y1_N1.coord_y = 9;
defparam clken_ctrl_X58_Y1_N1.coord_z = 1;
defparam clken_ctrl_X58_Y1_N1.ClkMux = 2'b10;
defparam clken_ctrl_X58_Y1_N1.ClkEnMux = 2'b10;

alta_clkenctrl clken_ctrl_X58_Y2_N0(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(),
	.ClkOut(\gclksw_inst|clkout_X58_Y2_SIG_VCC ));
defparam clken_ctrl_X58_Y2_N0.coord_x = 18;
defparam clken_ctrl_X58_Y2_N0.coord_y = 10;
defparam clken_ctrl_X58_Y2_N0.coord_z = 0;
defparam clken_ctrl_X58_Y2_N0.ClkMux = 2'b10;
defparam clken_ctrl_X58_Y2_N0.ClkEnMux = 2'b01;

alta_clkenctrl clken_ctrl_X59_Y1_N0(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(),
	.ClkOut(\gclksw_inst|clkout_X59_Y1_SIG_VCC ));
defparam clken_ctrl_X59_Y1_N0.coord_x = 17;
defparam clken_ctrl_X59_Y1_N0.coord_y = 9;
defparam clken_ctrl_X59_Y1_N0.coord_z = 0;
defparam clken_ctrl_X59_Y1_N0.ClkMux = 2'b10;
defparam clken_ctrl_X59_Y1_N0.ClkEnMux = 2'b01;

alta_clkenctrl clken_ctrl_X59_Y2_N0(
	.ClkIn(\gclksw_inst|clkout ),
	.ClkEn(),
	.ClkOut(\gclksw_inst|clkout_X59_Y2_SIG_VCC ));
defparam clken_ctrl_X59_Y2_N0.coord_x = 17;
defparam clken_ctrl_X59_Y2_N0.coord_y = 10;
defparam clken_ctrl_X59_Y2_N0.coord_z = 0;
defparam clken_ctrl_X59_Y2_N0.ClkMux = 2'b10;
defparam clken_ctrl_X59_Y2_N0.ClkEnMux = 2'b01;

alta_io_gclk \gclksw_inst|gclk_switch (
	.inclk(\gclksw_inst|gclk_switch__alta_gclksw__clkout ),
	.outclk(\gclksw_inst|clkout ));
defparam \gclksw_inst|gclk_switch .coord_x = 22;
defparam \gclksw_inst|gclk_switch .coord_y = 4;
defparam \gclksw_inst|gclk_switch .coord_z = 5;

alta_gclksw \gclksw_inst|gclk_switch__alta_gclksw (
	.resetn(vcc),
	.clkin0(\PIN_HSI~input_o ),
	.clkin1(\PIN_HSE~input_o ),
	.clkin2(\pll_inst|auto_generated|pll1_CLK_bus [0]),
	.clkin3(1'bx),
	.select({sys_ctrl_clkSource[1], sys_ctrl_clkSource[0]}),
	.clkout(\gclksw_inst|gclk_switch__alta_gclksw__clkout ));
defparam \gclksw_inst|gclk_switch__alta_gclksw .coord_x = 22;
defparam \gclksw_inst|gclk_switch__alta_gclksw .coord_y = 4;
defparam \gclksw_inst|gclk_switch__alta_gclksw .coord_z = 0;

alta_slice \macro_inst|Add0~12 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [6]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~11 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~12_combout ),
	.Cout(\macro_inst|Add0~13 ),
	.Q());
defparam \macro_inst|Add0~12 .coord_x = 17;
defparam \macro_inst|Add0~12 .coord_y = 10;
defparam \macro_inst|Add0~12 .coord_z = 6;
defparam \macro_inst|Add0~12 .mask = 16'hC30C;
defparam \macro_inst|Add0~12 .modeMux = 1'b1;
defparam \macro_inst|Add0~12 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~12 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~12 .BypassEn = 1'b0;
defparam \macro_inst|Add0~12 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~14 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [7]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~13 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~14_combout ),
	.Cout(\macro_inst|Add0~15 ),
	.Q());
defparam \macro_inst|Add0~14 .coord_x = 17;
defparam \macro_inst|Add0~14 .coord_y = 10;
defparam \macro_inst|Add0~14 .coord_z = 7;
defparam \macro_inst|Add0~14 .mask = 16'h3C3F;
defparam \macro_inst|Add0~14 .modeMux = 1'b1;
defparam \macro_inst|Add0~14 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~14 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~14 .BypassEn = 1'b0;
defparam \macro_inst|Add0~14 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~18 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [9]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~17 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~18_combout ),
	.Cout(\macro_inst|Add0~19 ),
	.Q());
defparam \macro_inst|Add0~18 .coord_x = 17;
defparam \macro_inst|Add0~18 .coord_y = 10;
defparam \macro_inst|Add0~18 .coord_z = 9;
defparam \macro_inst|Add0~18 .mask = 16'h3C3F;
defparam \macro_inst|Add0~18 .modeMux = 1'b1;
defparam \macro_inst|Add0~18 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~18 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~18 .BypassEn = 1'b0;
defparam \macro_inst|Add0~18 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~20 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [10]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~19 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~20_combout ),
	.Cout(\macro_inst|Add0~21 ),
	.Q());
defparam \macro_inst|Add0~20 .coord_x = 17;
defparam \macro_inst|Add0~20 .coord_y = 10;
defparam \macro_inst|Add0~20 .coord_z = 10;
defparam \macro_inst|Add0~20 .mask = 16'hC30C;
defparam \macro_inst|Add0~20 .modeMux = 1'b1;
defparam \macro_inst|Add0~20 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~20 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~20 .BypassEn = 1'b0;
defparam \macro_inst|Add0~20 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~24 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [12]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~23 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~24_combout ),
	.Cout(\macro_inst|Add0~25 ),
	.Q());
defparam \macro_inst|Add0~24 .coord_x = 17;
defparam \macro_inst|Add0~24 .coord_y = 10;
defparam \macro_inst|Add0~24 .coord_z = 12;
defparam \macro_inst|Add0~24 .mask = 16'hC30C;
defparam \macro_inst|Add0~24 .modeMux = 1'b1;
defparam \macro_inst|Add0~24 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~24 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~24 .BypassEn = 1'b0;
defparam \macro_inst|Add0~24 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~28 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [14]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~27 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~28_combout ),
	.Cout(\macro_inst|Add0~29 ),
	.Q());
defparam \macro_inst|Add0~28 .coord_x = 17;
defparam \macro_inst|Add0~28 .coord_y = 10;
defparam \macro_inst|Add0~28 .coord_z = 14;
defparam \macro_inst|Add0~28 .mask = 16'hC30C;
defparam \macro_inst|Add0~28 .modeMux = 1'b1;
defparam \macro_inst|Add0~28 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~28 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~28 .BypassEn = 1'b0;
defparam \macro_inst|Add0~28 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~34 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [17]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~33 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~34_combout ),
	.Cout(\macro_inst|Add0~35 ),
	.Q());
defparam \macro_inst|Add0~34 .coord_x = 17;
defparam \macro_inst|Add0~34 .coord_y = 9;
defparam \macro_inst|Add0~34 .coord_z = 1;
defparam \macro_inst|Add0~34 .mask = 16'h3C3F;
defparam \macro_inst|Add0~34 .modeMux = 1'b1;
defparam \macro_inst|Add0~34 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~34 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~34 .BypassEn = 1'b0;
defparam \macro_inst|Add0~34 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~36 (
	.A(\macro_inst|flow_cnt [18]),
	.B(vcc),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~35 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~36_combout ),
	.Cout(\macro_inst|Add0~37 ),
	.Q());
defparam \macro_inst|Add0~36 .coord_x = 17;
defparam \macro_inst|Add0~36 .coord_y = 9;
defparam \macro_inst|Add0~36 .coord_z = 2;
defparam \macro_inst|Add0~36 .mask = 16'hA50A;
defparam \macro_inst|Add0~36 .modeMux = 1'b1;
defparam \macro_inst|Add0~36 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~36 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~36 .BypassEn = 1'b0;
defparam \macro_inst|Add0~36 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~38 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [19]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~37 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~38_combout ),
	.Cout(\macro_inst|Add0~39 ),
	.Q());
defparam \macro_inst|Add0~38 .coord_x = 17;
defparam \macro_inst|Add0~38 .coord_y = 9;
defparam \macro_inst|Add0~38 .coord_z = 3;
defparam \macro_inst|Add0~38 .mask = 16'h3C3F;
defparam \macro_inst|Add0~38 .modeMux = 1'b1;
defparam \macro_inst|Add0~38 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~38 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~38 .BypassEn = 1'b0;
defparam \macro_inst|Add0~38 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~40 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [20]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~39 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~40_combout ),
	.Cout(\macro_inst|Add0~41 ),
	.Q());
defparam \macro_inst|Add0~40 .coord_x = 17;
defparam \macro_inst|Add0~40 .coord_y = 9;
defparam \macro_inst|Add0~40 .coord_z = 4;
defparam \macro_inst|Add0~40 .mask = 16'hC30C;
defparam \macro_inst|Add0~40 .modeMux = 1'b1;
defparam \macro_inst|Add0~40 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~40 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~40 .BypassEn = 1'b0;
defparam \macro_inst|Add0~40 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~42 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [21]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~41 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~42_combout ),
	.Cout(\macro_inst|Add0~43 ),
	.Q());
defparam \macro_inst|Add0~42 .coord_x = 17;
defparam \macro_inst|Add0~42 .coord_y = 9;
defparam \macro_inst|Add0~42 .coord_z = 5;
defparam \macro_inst|Add0~42 .mask = 16'h3C3F;
defparam \macro_inst|Add0~42 .modeMux = 1'b1;
defparam \macro_inst|Add0~42 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~42 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~42 .BypassEn = 1'b0;
defparam \macro_inst|Add0~42 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~44 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [22]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~43 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~44_combout ),
	.Cout(\macro_inst|Add0~45 ),
	.Q());
defparam \macro_inst|Add0~44 .coord_x = 17;
defparam \macro_inst|Add0~44 .coord_y = 9;
defparam \macro_inst|Add0~44 .coord_z = 6;
defparam \macro_inst|Add0~44 .mask = 16'hC30C;
defparam \macro_inst|Add0~44 .modeMux = 1'b1;
defparam \macro_inst|Add0~44 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~44 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~44 .BypassEn = 1'b0;
defparam \macro_inst|Add0~44 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~46 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [23]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~45 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~46_combout ),
	.Cout(\macro_inst|Add0~47 ),
	.Q());
defparam \macro_inst|Add0~46 .coord_x = 17;
defparam \macro_inst|Add0~46 .coord_y = 9;
defparam \macro_inst|Add0~46 .coord_z = 7;
defparam \macro_inst|Add0~46 .mask = 16'h3C3F;
defparam \macro_inst|Add0~46 .modeMux = 1'b1;
defparam \macro_inst|Add0~46 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~46 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~46 .BypassEn = 1'b0;
defparam \macro_inst|Add0~46 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~48 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [24]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~47 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~48_combout ),
	.Cout(\macro_inst|Add0~49 ),
	.Q());
defparam \macro_inst|Add0~48 .coord_x = 17;
defparam \macro_inst|Add0~48 .coord_y = 9;
defparam \macro_inst|Add0~48 .coord_z = 8;
defparam \macro_inst|Add0~48 .mask = 16'hC30C;
defparam \macro_inst|Add0~48 .modeMux = 1'b1;
defparam \macro_inst|Add0~48 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~48 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~48 .BypassEn = 1'b0;
defparam \macro_inst|Add0~48 .CarryEnb = 1'b0;

alta_slice \macro_inst|Add0~50 (
	.A(vcc),
	.B(\macro_inst|flow_cnt [25]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~49 ),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~50_combout ),
	.Cout(\macro_inst|Add0~51 ),
	.Q());
defparam \macro_inst|Add0~50 .coord_x = 17;
defparam \macro_inst|Add0~50 .coord_y = 9;
defparam \macro_inst|Add0~50 .coord_z = 9;
defparam \macro_inst|Add0~50 .mask = 16'h3C3F;
defparam \macro_inst|Add0~50 .modeMux = 1'b1;
defparam \macro_inst|Add0~50 .FeedbackMux = 1'b0;
defparam \macro_inst|Add0~50 .ShiftMux = 1'b0;
defparam \macro_inst|Add0~50 .BypassEn = 1'b0;
defparam \macro_inst|Add0~50 .CarryEnb = 1'b0;

alta_slice \macro_inst|Equal0~0 (
	.A(\macro_inst|flow_cnt [0]),
	.B(\macro_inst|flow_cnt [3]),
	.C(\macro_inst|flow_cnt [1]),
	.D(\macro_inst|flow_cnt [2]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~0_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~0 .coord_x = 18;
defparam \macro_inst|Equal0~0 .coord_y = 10;
defparam \macro_inst|Equal0~0 .coord_z = 2;
defparam \macro_inst|Equal0~0 .mask = 16'h8000;
defparam \macro_inst|Equal0~0 .modeMux = 1'b0;
defparam \macro_inst|Equal0~0 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~0 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~0 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~0 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~1 (
	.A(\macro_inst|flow_cnt [7]),
	.B(\macro_inst|flow_cnt [6]),
	.C(\macro_inst|flow_cnt [5]),
	.D(\macro_inst|flow_cnt [4]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~1_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~1 .coord_x = 18;
defparam \macro_inst|Equal0~1 .coord_y = 10;
defparam \macro_inst|Equal0~1 .coord_z = 14;
defparam \macro_inst|Equal0~1 .mask = 16'h2000;
defparam \macro_inst|Equal0~1 .modeMux = 1'b0;
defparam \macro_inst|Equal0~1 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~1 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~1 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~1 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~10 (
	.A(\macro_inst|Equal0~7_combout ),
	.B(\macro_inst|Equal0~9_combout ),
	.C(\macro_inst|Equal0~8_combout ),
	.D(\macro_inst|Equal0~4_combout ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~10_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~10 .coord_x = 18;
defparam \macro_inst|Equal0~10 .coord_y = 9;
defparam \macro_inst|Equal0~10 .coord_z = 11;
defparam \macro_inst|Equal0~10 .mask = 16'h8000;
defparam \macro_inst|Equal0~10 .modeMux = 1'b0;
defparam \macro_inst|Equal0~10 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~10 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~10 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~10 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~10_Duplicate (
	.A(\macro_inst|Equal0~9_combout ),
	.B(\macro_inst|Equal0~8_combout ),
	.C(\macro_inst|Equal0~7_combout ),
	.D(\macro_inst|Equal0~4_combout ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~10_Duplicate_12 ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~10_Duplicate .coord_x = 19;
defparam \macro_inst|Equal0~10_Duplicate .coord_y = 9;
defparam \macro_inst|Equal0~10_Duplicate .coord_z = 0;
defparam \macro_inst|Equal0~10_Duplicate .mask = 16'h8000;
defparam \macro_inst|Equal0~10_Duplicate .modeMux = 1'b0;
defparam \macro_inst|Equal0~10_Duplicate .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~10_Duplicate .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~10_Duplicate .BypassEn = 1'b0;
defparam \macro_inst|Equal0~10_Duplicate .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~2 (
	.A(\macro_inst|flow_cnt [10]),
	.B(\macro_inst|flow_cnt [8]),
	.C(\macro_inst|flow_cnt [9]),
	.D(\macro_inst|flow_cnt [11]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~2_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~2 .coord_x = 18;
defparam \macro_inst|Equal0~2 .coord_y = 10;
defparam \macro_inst|Equal0~2 .coord_z = 8;
defparam \macro_inst|Equal0~2 .mask = 16'h0020;
defparam \macro_inst|Equal0~2 .modeMux = 1'b0;
defparam \macro_inst|Equal0~2 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~2 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~2 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~2 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~3 (
	.A(\macro_inst|flow_cnt [12]),
	.B(\macro_inst|flow_cnt [14]),
	.C(\macro_inst|flow_cnt [15]),
	.D(\macro_inst|flow_cnt [13]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~3_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~3 .coord_x = 18;
defparam \macro_inst|Equal0~3 .coord_y = 10;
defparam \macro_inst|Equal0~3 .coord_z = 11;
defparam \macro_inst|Equal0~3 .mask = 16'h0008;
defparam \macro_inst|Equal0~3 .modeMux = 1'b0;
defparam \macro_inst|Equal0~3 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~3 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~3 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~3 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~4 (
	.A(\macro_inst|Equal0~0_combout ),
	.B(\macro_inst|Equal0~3_combout ),
	.C(\macro_inst|Equal0~2_combout ),
	.D(\macro_inst|Equal0~1_combout ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~4_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~4 .coord_x = 18;
defparam \macro_inst|Equal0~4 .coord_y = 10;
defparam \macro_inst|Equal0~4 .coord_z = 15;
defparam \macro_inst|Equal0~4 .mask = 16'h8000;
defparam \macro_inst|Equal0~4 .modeMux = 1'b0;
defparam \macro_inst|Equal0~4 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~4 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~4 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~4 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~5 (
	.A(\macro_inst|flow_cnt [19]),
	.B(\macro_inst|flow_cnt [18]),
	.C(\macro_inst|flow_cnt [17]),
	.D(\macro_inst|flow_cnt [16]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~5_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~5 .coord_x = 18;
defparam \macro_inst|Equal0~5 .coord_y = 9;
defparam \macro_inst|Equal0~5 .coord_z = 13;
defparam \macro_inst|Equal0~5 .mask = 16'h0080;
defparam \macro_inst|Equal0~5 .modeMux = 1'b0;
defparam \macro_inst|Equal0~5 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~5 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~5 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~5 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~7 (
	.A(\macro_inst|flow_cnt [22]),
	.B(\macro_inst|Equal0~5_combout ),
	.C(\macro_inst|flow_cnt [23]),
	.D(\macro_inst|Equal0~6_combout ),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~7_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~7 .coord_x = 18;
defparam \macro_inst|Equal0~7 .coord_y = 9;
defparam \macro_inst|Equal0~7 .coord_z = 7;
defparam \macro_inst|Equal0~7 .mask = 16'h8000;
defparam \macro_inst|Equal0~7 .modeMux = 1'b0;
defparam \macro_inst|Equal0~7 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~7 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~7 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~7 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~8 (
	.A(\macro_inst|flow_cnt [26]),
	.B(\macro_inst|flow_cnt [27]),
	.C(\macro_inst|flow_cnt [24]),
	.D(\macro_inst|flow_cnt [25]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~8_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~8 .coord_x = 18;
defparam \macro_inst|Equal0~8 .coord_y = 9;
defparam \macro_inst|Equal0~8 .coord_z = 4;
defparam \macro_inst|Equal0~8 .mask = 16'h1000;
defparam \macro_inst|Equal0~8 .modeMux = 1'b0;
defparam \macro_inst|Equal0~8 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~8 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~8 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~8 .CarryEnb = 1'b1;

alta_slice \macro_inst|Equal0~9 (
	.A(\macro_inst|flow_cnt [31]),
	.B(\macro_inst|flow_cnt [29]),
	.C(\macro_inst|flow_cnt [28]),
	.D(\macro_inst|flow_cnt [30]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Equal0~9_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|Equal0~9 .coord_x = 18;
defparam \macro_inst|Equal0~9 .coord_y = 9;
defparam \macro_inst|Equal0~9 .coord_z = 5;
defparam \macro_inst|Equal0~9 .mask = 16'h0001;
defparam \macro_inst|Equal0~9 .modeMux = 1'b0;
defparam \macro_inst|Equal0~9 .FeedbackMux = 1'b0;
defparam \macro_inst|Equal0~9 .ShiftMux = 1'b0;
defparam \macro_inst|Equal0~9 .BypassEn = 1'b0;
defparam \macro_inst|Equal0~9 .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[0] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [0]),
	.C(vcc),
	.D(vcc),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [0]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~0_combout ),
	.Cout(\macro_inst|Add0~1 ),
	.Q(\macro_inst|flow_cnt [0]));
defparam \macro_inst|flow_cnt[0] .coord_x = 17;
defparam \macro_inst|flow_cnt[0] .coord_y = 10;
defparam \macro_inst|flow_cnt[0] .coord_z = 0;
defparam \macro_inst|flow_cnt[0] .mask = 16'h33CC;
defparam \macro_inst|flow_cnt[0] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[0] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[0] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[0] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[0] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[10] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~20_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [10]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~3_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [10]));
defparam \macro_inst|flow_cnt[10] .coord_x = 18;
defparam \macro_inst|flow_cnt[10] .coord_y = 10;
defparam \macro_inst|flow_cnt[10] .coord_z = 10;
defparam \macro_inst|flow_cnt[10] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[10] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[10] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[10] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[10] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[10] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[11] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [11]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~21 ),
	.Qin(\macro_inst|flow_cnt [11]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~22_combout ),
	.Cout(\macro_inst|Add0~23 ),
	.Q(\macro_inst|flow_cnt [11]));
defparam \macro_inst|flow_cnt[11] .coord_x = 17;
defparam \macro_inst|flow_cnt[11] .coord_y = 10;
defparam \macro_inst|flow_cnt[11] .coord_z = 11;
defparam \macro_inst|flow_cnt[11] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[11] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[11] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[11] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[11] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[11] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[12] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~24_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [12]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~4_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [12]));
defparam \macro_inst|flow_cnt[12] .coord_x = 18;
defparam \macro_inst|flow_cnt[12] .coord_y = 10;
defparam \macro_inst|flow_cnt[12] .coord_z = 12;
defparam \macro_inst|flow_cnt[12] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[12] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[12] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[12] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[12] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[12] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[13] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [13]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~25 ),
	.Qin(\macro_inst|flow_cnt [13]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~26_combout ),
	.Cout(\macro_inst|Add0~27 ),
	.Q(\macro_inst|flow_cnt [13]));
defparam \macro_inst|flow_cnt[13] .coord_x = 17;
defparam \macro_inst|flow_cnt[13] .coord_y = 10;
defparam \macro_inst|flow_cnt[13] .coord_z = 13;
defparam \macro_inst|flow_cnt[13] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[13] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[13] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[13] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[13] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[13] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[14] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~28_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [14]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~5_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [14]));
defparam \macro_inst|flow_cnt[14] .coord_x = 18;
defparam \macro_inst|flow_cnt[14] .coord_y = 10;
defparam \macro_inst|flow_cnt[14] .coord_z = 13;
defparam \macro_inst|flow_cnt[14] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[14] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[14] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[14] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[14] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[14] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[15] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [15]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~29 ),
	.Qin(\macro_inst|flow_cnt [15]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~30_combout ),
	.Cout(\macro_inst|Add0~31 ),
	.Q(\macro_inst|flow_cnt [15]));
defparam \macro_inst|flow_cnt[15] .coord_x = 17;
defparam \macro_inst|flow_cnt[15] .coord_y = 10;
defparam \macro_inst|flow_cnt[15] .coord_z = 15;
defparam \macro_inst|flow_cnt[15] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[15] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[15] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[15] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[15] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[15] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[16] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [16]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~31 ),
	.Qin(\macro_inst|flow_cnt [16]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~32_combout ),
	.Cout(\macro_inst|Add0~33 ),
	.Q(\macro_inst|flow_cnt [16]));
defparam \macro_inst|flow_cnt[16] .coord_x = 17;
defparam \macro_inst|flow_cnt[16] .coord_y = 9;
defparam \macro_inst|flow_cnt[16] .coord_z = 0;
defparam \macro_inst|flow_cnt[16] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[16] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[16] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[16] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[16] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[16] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[17] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~34_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [17]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~6_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [17]));
defparam \macro_inst|flow_cnt[17] .coord_x = 18;
defparam \macro_inst|flow_cnt[17] .coord_y = 9;
defparam \macro_inst|flow_cnt[17] .coord_z = 3;
defparam \macro_inst|flow_cnt[17] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[17] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[17] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[17] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[17] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[17] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[18] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~36_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [18]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~7_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [18]));
defparam \macro_inst|flow_cnt[18] .coord_x = 18;
defparam \macro_inst|flow_cnt[18] .coord_y = 9;
defparam \macro_inst|flow_cnt[18] .coord_z = 9;
defparam \macro_inst|flow_cnt[18] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[18] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[18] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[18] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[18] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[18] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[19] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~38_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [19]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~8_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [19]));
defparam \macro_inst|flow_cnt[19] .coord_x = 18;
defparam \macro_inst|flow_cnt[19] .coord_y = 9;
defparam \macro_inst|flow_cnt[19] .coord_z = 12;
defparam \macro_inst|flow_cnt[19] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[19] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[19] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[19] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[19] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[19] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[1] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [1]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~1 ),
	.Qin(\macro_inst|flow_cnt [1]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~2_combout ),
	.Cout(\macro_inst|Add0~3 ),
	.Q(\macro_inst|flow_cnt [1]));
defparam \macro_inst|flow_cnt[1] .coord_x = 17;
defparam \macro_inst|flow_cnt[1] .coord_y = 10;
defparam \macro_inst|flow_cnt[1] .coord_z = 1;
defparam \macro_inst|flow_cnt[1] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[1] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[1] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[1] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[1] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[1] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[20] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~40_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [20]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~9_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [20]));
defparam \macro_inst|flow_cnt[20] .coord_x = 18;
defparam \macro_inst|flow_cnt[20] .coord_y = 9;
defparam \macro_inst|flow_cnt[20] .coord_z = 14;
defparam \macro_inst|flow_cnt[20] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[20] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[20] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[20] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[20] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[20] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[21] (
	.A(vcc),
	.B(\macro_inst|Add0~42_combout ),
	.C(\macro_inst|Equal0~10_combout ),
	.D(vcc),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [21]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~10_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [21]));
defparam \macro_inst|flow_cnt[21] .coord_x = 18;
defparam \macro_inst|flow_cnt[21] .coord_y = 9;
defparam \macro_inst|flow_cnt[21] .coord_z = 10;
defparam \macro_inst|flow_cnt[21] .mask = 16'h0C0C;
defparam \macro_inst|flow_cnt[21] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[21] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[21] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[21] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[21] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[22] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~44_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [22]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~11_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [22]));
defparam \macro_inst|flow_cnt[22] .coord_x = 18;
defparam \macro_inst|flow_cnt[22] .coord_y = 9;
defparam \macro_inst|flow_cnt[22] .coord_z = 6;
defparam \macro_inst|flow_cnt[22] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[22] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[22] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[22] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[22] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[22] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[23] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~46_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [23]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~12_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [23]));
defparam \macro_inst|flow_cnt[23] .coord_x = 18;
defparam \macro_inst|flow_cnt[23] .coord_y = 9;
defparam \macro_inst|flow_cnt[23] .coord_z = 0;
defparam \macro_inst|flow_cnt[23] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[23] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[23] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[23] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[23] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[23] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[24] (
	.A(vcc),
	.B(\macro_inst|Equal0~10_combout ),
	.C(vcc),
	.D(\macro_inst|Add0~48_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [24]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~13_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [24]));
defparam \macro_inst|flow_cnt[24] .coord_x = 18;
defparam \macro_inst|flow_cnt[24] .coord_y = 9;
defparam \macro_inst|flow_cnt[24] .coord_z = 8;
defparam \macro_inst|flow_cnt[24] .mask = 16'h3300;
defparam \macro_inst|flow_cnt[24] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[24] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[24] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[24] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[24] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[25] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~50_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [25]),
	.Clk(\gclksw_inst|clkout_X58_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~14_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [25]));
defparam \macro_inst|flow_cnt[25] .coord_x = 18;
defparam \macro_inst|flow_cnt[25] .coord_y = 9;
defparam \macro_inst|flow_cnt[25] .coord_z = 1;
defparam \macro_inst|flow_cnt[25] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[25] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[25] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[25] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[25] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[25] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[26] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [26]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~51 ),
	.Qin(\macro_inst|flow_cnt [26]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~52_combout ),
	.Cout(\macro_inst|Add0~53 ),
	.Q(\macro_inst|flow_cnt [26]));
defparam \macro_inst|flow_cnt[26] .coord_x = 17;
defparam \macro_inst|flow_cnt[26] .coord_y = 9;
defparam \macro_inst|flow_cnt[26] .coord_z = 10;
defparam \macro_inst|flow_cnt[26] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[26] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[26] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[26] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[26] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[26] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[27] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [27]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~53 ),
	.Qin(\macro_inst|flow_cnt [27]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~54_combout ),
	.Cout(\macro_inst|Add0~55 ),
	.Q(\macro_inst|flow_cnt [27]));
defparam \macro_inst|flow_cnt[27] .coord_x = 17;
defparam \macro_inst|flow_cnt[27] .coord_y = 9;
defparam \macro_inst|flow_cnt[27] .coord_z = 11;
defparam \macro_inst|flow_cnt[27] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[27] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[27] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[27] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[27] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[27] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[28] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [28]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~55 ),
	.Qin(\macro_inst|flow_cnt [28]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~56_combout ),
	.Cout(\macro_inst|Add0~57 ),
	.Q(\macro_inst|flow_cnt [28]));
defparam \macro_inst|flow_cnt[28] .coord_x = 17;
defparam \macro_inst|flow_cnt[28] .coord_y = 9;
defparam \macro_inst|flow_cnt[28] .coord_z = 12;
defparam \macro_inst|flow_cnt[28] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[28] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[28] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[28] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[28] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[28] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[29] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [29]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~57 ),
	.Qin(\macro_inst|flow_cnt [29]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~58_combout ),
	.Cout(\macro_inst|Add0~59 ),
	.Q(\macro_inst|flow_cnt [29]));
defparam \macro_inst|flow_cnt[29] .coord_x = 17;
defparam \macro_inst|flow_cnt[29] .coord_y = 9;
defparam \macro_inst|flow_cnt[29] .coord_z = 13;
defparam \macro_inst|flow_cnt[29] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[29] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[29] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[29] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[29] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[29] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[2] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [2]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~3 ),
	.Qin(\macro_inst|flow_cnt [2]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~4_combout ),
	.Cout(\macro_inst|Add0~5 ),
	.Q(\macro_inst|flow_cnt [2]));
defparam \macro_inst|flow_cnt[2] .coord_x = 17;
defparam \macro_inst|flow_cnt[2] .coord_y = 10;
defparam \macro_inst|flow_cnt[2] .coord_z = 2;
defparam \macro_inst|flow_cnt[2] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[2] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[2] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[2] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[2] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[2] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[30] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [30]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~59 ),
	.Qin(\macro_inst|flow_cnt [30]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~60_combout ),
	.Cout(\macro_inst|Add0~61 ),
	.Q(\macro_inst|flow_cnt [30]));
defparam \macro_inst|flow_cnt[30] .coord_x = 17;
defparam \macro_inst|flow_cnt[30] .coord_y = 9;
defparam \macro_inst|flow_cnt[30] .coord_z = 14;
defparam \macro_inst|flow_cnt[30] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[30] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[30] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[30] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[30] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[30] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[31] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [31]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~61 ),
	.Qin(\macro_inst|flow_cnt [31]),
	.Clk(\gclksw_inst|clkout_X59_Y1_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~62_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [31]));
defparam \macro_inst|flow_cnt[31] .coord_x = 17;
defparam \macro_inst|flow_cnt[31] .coord_y = 9;
defparam \macro_inst|flow_cnt[31] .coord_z = 15;
defparam \macro_inst|flow_cnt[31] .mask = 16'h3C3C;
defparam \macro_inst|flow_cnt[31] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[31] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[31] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[31] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[31] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[3] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [3]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~5 ),
	.Qin(\macro_inst|flow_cnt [3]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~6_combout ),
	.Cout(\macro_inst|Add0~7 ),
	.Q(\macro_inst|flow_cnt [3]));
defparam \macro_inst|flow_cnt[3] .coord_x = 17;
defparam \macro_inst|flow_cnt[3] .coord_y = 10;
defparam \macro_inst|flow_cnt[3] .coord_z = 3;
defparam \macro_inst|flow_cnt[3] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[3] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[3] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[3] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[3] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[3] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[4] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [4]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~7 ),
	.Qin(\macro_inst|flow_cnt [4]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~8_combout ),
	.Cout(\macro_inst|Add0~9 ),
	.Q(\macro_inst|flow_cnt [4]));
defparam \macro_inst|flow_cnt[4] .coord_x = 17;
defparam \macro_inst|flow_cnt[4] .coord_y = 10;
defparam \macro_inst|flow_cnt[4] .coord_z = 4;
defparam \macro_inst|flow_cnt[4] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[4] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[4] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[4] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[4] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[4] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[5] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [5]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~9 ),
	.Qin(\macro_inst|flow_cnt [5]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~10_combout ),
	.Cout(\macro_inst|Add0~11 ),
	.Q(\macro_inst|flow_cnt [5]));
defparam \macro_inst|flow_cnt[5] .coord_x = 17;
defparam \macro_inst|flow_cnt[5] .coord_y = 10;
defparam \macro_inst|flow_cnt[5] .coord_z = 5;
defparam \macro_inst|flow_cnt[5] .mask = 16'h3C3F;
defparam \macro_inst|flow_cnt[5] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[5] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[5] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[5] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[5] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[6] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~12_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [6]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~1_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [6]));
defparam \macro_inst|flow_cnt[6] .coord_x = 18;
defparam \macro_inst|flow_cnt[6] .coord_y = 10;
defparam \macro_inst|flow_cnt[6] .coord_z = 3;
defparam \macro_inst|flow_cnt[6] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[6] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[6] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[6] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[6] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[6] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[7] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~14_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [7]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~0_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [7]));
defparam \macro_inst|flow_cnt[7] .coord_x = 18;
defparam \macro_inst|flow_cnt[7] .coord_y = 10;
defparam \macro_inst|flow_cnt[7] .coord_z = 4;
defparam \macro_inst|flow_cnt[7] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[7] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[7] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[7] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[7] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[7] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_cnt[8] (
	.A(vcc),
	.B(\macro_inst|flow_cnt [8]),
	.C(vcc),
	.D(vcc),
	.Cin(\macro_inst|Add0~15 ),
	.Qin(\macro_inst|flow_cnt [8]),
	.Clk(\gclksw_inst|clkout_X59_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X59_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|Add0~16_combout ),
	.Cout(\macro_inst|Add0~17 ),
	.Q(\macro_inst|flow_cnt [8]));
defparam \macro_inst|flow_cnt[8] .coord_x = 17;
defparam \macro_inst|flow_cnt[8] .coord_y = 10;
defparam \macro_inst|flow_cnt[8] .coord_z = 8;
defparam \macro_inst|flow_cnt[8] .mask = 16'hC30C;
defparam \macro_inst|flow_cnt[8] .modeMux = 1'b1;
defparam \macro_inst|flow_cnt[8] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[8] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[8] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[8] .CarryEnb = 1'b0;

alta_slice \macro_inst|flow_cnt[9] (
	.A(vcc),
	.B(vcc),
	.C(\macro_inst|Add0~18_combout ),
	.D(\macro_inst|Equal0~10_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_cnt [9]),
	.Clk(\gclksw_inst|clkout_X58_Y2_SIG_VCC ),
	.AsyncReset(AsyncReset_X58_Y2_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_cnt~2_combout ),
	.Cout(),
	.Q(\macro_inst|flow_cnt [9]));
defparam \macro_inst|flow_cnt[9] .coord_x = 18;
defparam \macro_inst|flow_cnt[9] .coord_y = 10;
defparam \macro_inst|flow_cnt[9] .coord_z = 9;
defparam \macro_inst|flow_cnt[9] .mask = 16'h00F0;
defparam \macro_inst|flow_cnt[9] .modeMux = 1'b0;
defparam \macro_inst|flow_cnt[9] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_cnt[9] .ShiftMux = 1'b0;
defparam \macro_inst|flow_cnt[9] .BypassEn = 1'b0;
defparam \macro_inst|flow_cnt[9] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_pos[0] (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(\macro_inst|flow_pos [3]),
	.Cin(),
	.Qin(\macro_inst|flow_pos [0]),
	.Clk(\gclksw_inst|clkout__macro_inst|Equal0~10_Duplicate_12_X57_Y1_SIG_SIG ),
	.AsyncReset(AsyncReset_X57_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_pos[0]~0_combout ),
	.Cout(),
	.Q(\macro_inst|flow_pos [0]));
defparam \macro_inst|flow_pos[0] .coord_x = 19;
defparam \macro_inst|flow_pos[0] .coord_y = 9;
defparam \macro_inst|flow_pos[0] .coord_z = 15;
defparam \macro_inst|flow_pos[0] .mask = 16'h00FF;
defparam \macro_inst|flow_pos[0] .modeMux = 1'b0;
defparam \macro_inst|flow_pos[0] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_pos[0] .ShiftMux = 1'b0;
defparam \macro_inst|flow_pos[0] .BypassEn = 1'b0;
defparam \macro_inst|flow_pos[0] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_pos[1] (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(\macro_inst|flow_pos[1]~1_combout ),
	.Cin(),
	.Qin(\macro_inst|flow_pos [1]),
	.Clk(\gclksw_inst|clkout__macro_inst|Equal0~10_combout_X58_Y1_SIG_SIG ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_pos[1]~feeder_combout ),
	.Cout(),
	.Q(\macro_inst|flow_pos [1]));
defparam \macro_inst|flow_pos[1] .coord_x = 18;
defparam \macro_inst|flow_pos[1] .coord_y = 9;
defparam \macro_inst|flow_pos[1] .coord_z = 2;
defparam \macro_inst|flow_pos[1] .mask = 16'hFF00;
defparam \macro_inst|flow_pos[1] .modeMux = 1'b0;
defparam \macro_inst|flow_pos[1] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_pos[1] .ShiftMux = 1'b0;
defparam \macro_inst|flow_pos[1] .BypassEn = 1'b0;
defparam \macro_inst|flow_pos[1] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_pos[1]~1 (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(\macro_inst|flow_pos [0]),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_pos[1]~1_combout ),
	.Cout(),
	.Q());
defparam \macro_inst|flow_pos[1]~1 .coord_x = 19;
defparam \macro_inst|flow_pos[1]~1 .coord_y = 9;
defparam \macro_inst|flow_pos[1]~1 .coord_z = 7;
defparam \macro_inst|flow_pos[1]~1 .mask = 16'h00FF;
defparam \macro_inst|flow_pos[1]~1 .modeMux = 1'b0;
defparam \macro_inst|flow_pos[1]~1 .FeedbackMux = 1'b0;
defparam \macro_inst|flow_pos[1]~1 .ShiftMux = 1'b0;
defparam \macro_inst|flow_pos[1]~1 .BypassEn = 1'b0;
defparam \macro_inst|flow_pos[1]~1 .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_pos[2] (
	.A(\macro_inst|flow_cnt [21]),
	.B(vcc),
	.C(\macro_inst|flow_pos [1]),
	.D(\macro_inst|flow_cnt [20]),
	.Cin(),
	.Qin(\macro_inst|flow_pos [2]),
	.Clk(\gclksw_inst|clkout__macro_inst|Equal0~10_combout_X58_Y1_SIG_SIG ),
	.AsyncReset(AsyncReset_X58_Y1_GND),
	.SyncReset(SyncReset_X58_Y1_GND),
	.ShiftData(),
	.SyncLoad(SyncLoad_X58_Y1_VCC),
	.LutOut(\macro_inst|Equal0~6_combout ),
	.Cout(),
	.Q(\macro_inst|flow_pos [2]));
defparam \macro_inst|flow_pos[2] .coord_x = 18;
defparam \macro_inst|flow_pos[2] .coord_y = 9;
defparam \macro_inst|flow_pos[2] .coord_z = 15;
defparam \macro_inst|flow_pos[2] .mask = 16'hAA00;
defparam \macro_inst|flow_pos[2] .modeMux = 1'b0;
defparam \macro_inst|flow_pos[2] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_pos[2] .ShiftMux = 1'b0;
defparam \macro_inst|flow_pos[2] .BypassEn = 1'b1;
defparam \macro_inst|flow_pos[2] .CarryEnb = 1'b1;

alta_slice \macro_inst|flow_pos[3] (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(\macro_inst|flow_pos [2]),
	.Cin(),
	.Qin(\macro_inst|flow_pos [3]),
	.Clk(\gclksw_inst|clkout__macro_inst|Equal0~10_Duplicate_12_X57_Y1_SIG_SIG ),
	.AsyncReset(AsyncReset_X57_Y1_GND),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\macro_inst|flow_pos[3]~feeder_combout ),
	.Cout(),
	.Q(\macro_inst|flow_pos [3]));
defparam \macro_inst|flow_pos[3] .coord_x = 19;
defparam \macro_inst|flow_pos[3] .coord_y = 9;
defparam \macro_inst|flow_pos[3] .coord_z = 14;
defparam \macro_inst|flow_pos[3] .mask = 16'hFF00;
defparam \macro_inst|flow_pos[3] .modeMux = 1'b0;
defparam \macro_inst|flow_pos[3] .FeedbackMux = 1'b0;
defparam \macro_inst|flow_pos[3] .ShiftMux = 1'b0;
defparam \macro_inst|flow_pos[3] .BypassEn = 1'b0;
defparam \macro_inst|flow_pos[3] .CarryEnb = 1'b1;

alta_pllve \pll_inst|auto_generated|pll1 (
	.clkin(\PIN_HSE~input_o ),
	.clkfb(\pll_inst|auto_generated|pll1~FBOUT ),
	.pfden(vcc),
	.resetn(!\PLL_ENABLE~clkctrl_outclk ),
	.phasecounterselect({gnd, gnd, gnd}),
	.phaseupdown(gnd),
	.phasestep(gnd),
	.scanclk(gnd),
	.scanclkena(vcc),
	.scandata(gnd),
	.configupdate(gnd),
	.scandataout(),
	.scandone(),
	.phasedone(),
	.clkout0(\pll_inst|auto_generated|pll1_CLK_bus [0]),
	.clkout1(\pll_inst|auto_generated|pll1_CLK_bus [1]),
	.clkout2(\pll_inst|auto_generated|pll1_CLK_bus [2]),
	.clkout3(\pll_inst|auto_generated|pll1_CLK_bus [3]),
	.clkout4(\pll_inst|auto_generated|pll1_CLK_bus [4]),
	.clkfbout(\pll_inst|auto_generated|pll1~FBOUT ),
	.lock(\pll_inst|auto_generated|pll1~LOCKED ));
defparam \pll_inst|auto_generated|pll1 .coord_x = 22;
defparam \pll_inst|auto_generated|pll1 .coord_y = 5;
defparam \pll_inst|auto_generated|pll1 .coord_z = 0;
defparam \pll_inst|auto_generated|pll1 .CLKIN_HIGH = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKIN_LOW = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKIN_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKIN_BYPASS = 1'b1;
defparam \pll_inst|auto_generated|pll1 .CLKFB_HIGH = 8'b00011000;
defparam \pll_inst|auto_generated|pll1 .CLKFB_LOW = 8'b00011000;
defparam \pll_inst|auto_generated|pll1 .CLKFB_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKFB_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKDIV0_EN = 1'b1;
defparam \pll_inst|auto_generated|pll1 .CLKDIV1_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKDIV2_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKDIV3_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKDIV4_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_HIGH = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_LOW = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_HIGH = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_LOW = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_HIGH = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_LOW = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_HIGH = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_LOW = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_HIGH = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_LOW = 8'b11111111;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_TRIM = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_BYPASS = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT0_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .CLKFB_DEL = 8'b00000000;
defparam \pll_inst|auto_generated|pll1 .CLKFB_PHASE = 3'b000;
defparam \pll_inst|auto_generated|pll1 .FEEDBACK_MODE = 3'b100;
defparam \pll_inst|auto_generated|pll1 .FBDELAY_VAL = 3'b100;
defparam \pll_inst|auto_generated|pll1 .PLLOUTP_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .PLLOUTN_EN = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT1_CASCADE = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT2_CASCADE = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT3_CASCADE = 1'b0;
defparam \pll_inst|auto_generated|pll1 .CLKOUT4_CASCADE = 1'b0;
defparam \pll_inst|auto_generated|pll1 .VCO_POST_DIV = 1'b1;
defparam \pll_inst|auto_generated|pll1 .REG_CTRL = 2'b00;
defparam \pll_inst|auto_generated|pll1 .CP = 3'b100;
defparam \pll_inst|auto_generated|pll1 .RREF = 2'b01;
defparam \pll_inst|auto_generated|pll1 .RVI = 2'b01;
defparam \pll_inst|auto_generated|pll1 .IVCO = 3'b010;
defparam \pll_inst|auto_generated|pll1 .PLL_EN_FLAG = 1'b1;

alta_slice \pll_inst|auto_generated|pll_lock_sync (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(vcc),
	.Cin(),
	.Qin(\pll_inst|auto_generated|pll_lock_sync~q ),
	.Clk(\pll_inst|auto_generated|pll1~LOCKED_X49_Y1_SIG_VCC ),
	.AsyncReset(\PLL_ENABLE~clkctrl_outclk__AsyncReset_X49_Y1_SIG ),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(\pll_inst|auto_generated|pll_lock_sync~feeder_combout ),
	.Cout(),
	.Q(\pll_inst|auto_generated|pll_lock_sync~q ));
defparam \pll_inst|auto_generated|pll_lock_sync .coord_x = 19;
defparam \pll_inst|auto_generated|pll_lock_sync .coord_y = 4;
defparam \pll_inst|auto_generated|pll_lock_sync .coord_z = 15;
defparam \pll_inst|auto_generated|pll_lock_sync .mask = 16'hFFFF;
defparam \pll_inst|auto_generated|pll_lock_sync .modeMux = 1'b0;
defparam \pll_inst|auto_generated|pll_lock_sync .FeedbackMux = 1'b0;
defparam \pll_inst|auto_generated|pll_lock_sync .ShiftMux = 1'b0;
defparam \pll_inst|auto_generated|pll_lock_sync .BypassEn = 1'b0;
defparam \pll_inst|auto_generated|pll_lock_sync .CarryEnb = 1'b1;

alta_syncctrl syncload_ctrl_X58_Y1(
	.Din(),
	.Dout(SyncLoad_X58_Y1_VCC));
defparam syncload_ctrl_X58_Y1.coord_x = 18;
defparam syncload_ctrl_X58_Y1.coord_y = 9;
defparam syncload_ctrl_X58_Y1.coord_z = 1;
defparam syncload_ctrl_X58_Y1.SyncCtrlMux = 2'b01;

alta_syncctrl syncreset_ctrl_X58_Y1(
	.Din(),
	.Dout(SyncReset_X58_Y1_GND));
defparam syncreset_ctrl_X58_Y1.coord_x = 18;
defparam syncreset_ctrl_X58_Y1.coord_y = 9;
defparam syncreset_ctrl_X58_Y1.coord_z = 0;
defparam syncreset_ctrl_X58_Y1.SyncCtrlMux = 2'b00;

alta_slice \sys_ctrl_clkSource[0] (
	.A(vcc),
	.B(vcc),
	.C(vcc),
	.D(vcc),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(sys_ctrl_clkSource[0]),
	.Cout(),
	.Q());
defparam \sys_ctrl_clkSource[0] .coord_x = 18;
defparam \sys_ctrl_clkSource[0] .coord_y = 4;
defparam \sys_ctrl_clkSource[0] .coord_z = 0;
defparam \sys_ctrl_clkSource[0] .mask = 16'hFFFF;
defparam \sys_ctrl_clkSource[0] .modeMux = 1'b0;
defparam \sys_ctrl_clkSource[0] .FeedbackMux = 1'b0;
defparam \sys_ctrl_clkSource[0] .ShiftMux = 1'b0;
defparam \sys_ctrl_clkSource[0] .BypassEn = 1'b0;
defparam \sys_ctrl_clkSource[0] .CarryEnb = 1'b1;

alta_slice \sys_ctrl_clkSource[1] (
	.A(\PLL_LOCK~combout ),
	.B(vcc),
	.C(vcc),
	.D(vcc),
	.Cin(),
	.Qin(),
	.Clk(),
	.AsyncReset(),
	.SyncReset(),
	.ShiftData(),
	.SyncLoad(),
	.LutOut(sys_ctrl_clkSource[1]),
	.Cout(),
	.Q());
defparam \sys_ctrl_clkSource[1] .coord_x = 18;
defparam \sys_ctrl_clkSource[1] .coord_y = 4;
defparam \sys_ctrl_clkSource[1] .coord_z = 1;
defparam \sys_ctrl_clkSource[1] .mask = 16'hAAAA;
defparam \sys_ctrl_clkSource[1] .modeMux = 1'b0;
defparam \sys_ctrl_clkSource[1] .FeedbackMux = 1'b0;
defparam \sys_ctrl_clkSource[1] .ShiftMux = 1'b0;
defparam \sys_ctrl_clkSource[1] .BypassEn = 1'b0;
defparam \sys_ctrl_clkSource[1] .CarryEnb = 1'b1;

endmodule
