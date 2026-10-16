// One outstanding AHB transfer. Toggle handshakes retain completion across
// SYS/BUS clocks, including SYS switching to slow HSI during downloads.
module ahb2apb #(parameter integer ADDR_BITS=32, DATA_BITS=32) (
  input reset, ahb_clock, ahb_hmastlock,
  input [1:0] ahb_htrans,
  input ahb_hsel, ahb_hready, ahb_hwrite,
  input [ADDR_BITS-1:0] ahb_haddr,
  input [2:0] ahb_hsize, ahb_hburst,
  input [3:0] ahb_hprot,
  input [DATA_BITS-1:0] ahb_hwdata,
  output reg [DATA_BITS-1:0] ahb_hrdata,
  output reg ahb_hreadyout, ahb_hresp,
  input apb_clock,
  output reg apb_psel, apb_penable, apb_pwrite,
  output reg [ADDR_BITS-1:0] apb_paddr,
  output reg [DATA_BITS-1:0] apb_pwdata,
  output reg [3:0] apb_pstrb,
  output reg [2:0] apb_pprot,
  input apb_pready, apb_pslverr,
  input [DATA_BITS-1:0] apb_prdata
);
localparam H_IDLE=0, H_DATA=1, H_WAIT=2, H_ERROR=3;
localparam P_IDLE=0, P_SETUP=1, P_ACCESS=2;
reg [1:0] hstate, pstate;
reg request, acknowledge;
(* async_reg = "true" *) reg [1:0] request_sync, acknowledge_sync;
reg [ADDR_BITS-1:0] haddr;
reg [DATA_BITS-1:0] hwdata, response_data;
reg hwrite, response_error;
reg [2:0] hsize, hprot;

always @(posedge ahb_clock or posedge reset) begin
  if (reset) acknowledge_sync <= 0;
  else acknowledge_sync <= {acknowledge_sync[0], acknowledge};
end
always @(posedge apb_clock or posedge reset) begin
  if (reset) request_sync <= 0;
  else request_sync <= {request_sync[0], request};
end
always @(posedge ahb_clock or posedge reset) begin
  if (reset) begin
    hstate <= H_IDLE; request <= 0;
    ahb_hreadyout <= 1; ahb_hresp <= 0; ahb_hrdata <= 0;
    haddr <= 0; hwrite <= 0; hsize <= 0; hprot <= 0; hwdata <= 0;
  end else begin
    case (hstate)
      H_IDLE: begin
        ahb_hresp <= 0;
        if (ahb_hsel && ahb_htrans[1] && ahb_hreadyout) begin
          haddr <= ahb_haddr; hwrite <= ahb_hwrite;
          hsize <= ahb_hsize; hprot <= ahb_hprot[2:0];
          ahb_hreadyout <= 0; hstate <= H_DATA;
        end
      end
      H_DATA: begin
        // Write data follows its AHB address phase by one cycle.
        hwdata <= ahb_hwdata;
        request <= ~request;
        hstate <= H_WAIT;
      end
      H_WAIT: if (acknowledge_sync[1] == request) begin
        ahb_hrdata <= response_data;
        ahb_hresp <= response_error;
        if (response_error) hstate <= H_ERROR;
        else begin ahb_hreadyout <= 1; hstate <= H_IDLE; end
      end
      H_ERROR: begin ahb_hreadyout <= 1; hstate <= H_IDLE; end
      default: begin ahb_hreadyout <= 1; ahb_hresp <= 0; hstate <= H_IDLE; end
    endcase
  end
end
always @(posedge apb_clock or posedge reset) begin
  if (reset) begin
    pstate <= P_IDLE; acknowledge <= 0;
    apb_psel <= 0; apb_penable <= 0; apb_pwrite <= 0;
    apb_paddr <= 0; apb_pwdata <= 0; apb_pstrb <= 0; apb_pprot <= 0;
    response_data <= 0; response_error <= 0;
  end else begin
    case (pstate)
      P_IDLE: if (request_sync[1] != acknowledge) begin
        apb_psel <= 1; apb_penable <= 0;
        apb_paddr <= {haddr[ADDR_BITS-1:2],2'b00};
        apb_pwrite <= hwrite; apb_pwdata <= hwdata; apb_pprot <= hprot;
        apb_pstrb <= hwrite ? ((4'b1111 >> (4-(1 << hsize))) << haddr[1:0]) : 0;
        pstate <= P_SETUP;
      end
      P_SETUP: begin apb_penable <= 1; pstate <= P_ACCESS; end
      P_ACCESS: if (apb_pready) begin
        response_data <= apb_prdata; response_error <= apb_pslverr;
        acknowledge <= request_sync[1];
        apb_psel <= 0; apb_penable <= 0; pstate <= P_IDLE;
      end
      default: begin apb_psel <= 0; apb_penable <= 0; pstate <= P_IDLE; end
    endcase
  end
end
endmodule
