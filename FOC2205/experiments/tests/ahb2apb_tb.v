`timescale 1ns/1ps
module ahb2apb_tb;
reg reset=1, hc=0, pc=0;
real half_sys=2.5;
always begin #(half_sys) hc=~hc; end
always #5 pc=~pc;
reg [1:0] ht=0;
reg hw=0;
reg [31:0] ha=0, hd=0;
wire [31:0] hr, pa, pd;
wire ready, resp, ps, pe, pw;
wire [3:0] strb;
wire [2:0] prot;
reg [31:0] memory[0:255];
integer waits=0, target_wait=0, transfers=0, errors=0, i, before_count;
wire prdy=(waits>=target_wait);
wire [31:0] rd=memory[pa[9:2]];
ahb2apb dut(.reset(reset),.ahb_clock(hc),.ahb_hmastlock(1'b0),
 .ahb_htrans(ht),.ahb_hsel(1'b1),.ahb_hready(ready),.ahb_hwrite(hw),
 .ahb_haddr(ha),.ahb_hsize(3'd2),.ahb_hburst(3'd0),.ahb_hprot(4'b0011),
 .ahb_hwdata(hd),.ahb_hrdata(hr),.ahb_hreadyout(ready),.ahb_hresp(resp),
 .apb_clock(pc),.apb_psel(ps),.apb_penable(pe),.apb_pwrite(pw),
 .apb_paddr(pa),.apb_pwdata(pd),.apb_pstrb(strb),.apb_pprot(prot),
 .apb_pready(prdy),.apb_pslverr(1'b0),.apb_prdata(rd));
always @(posedge pc) begin
 if (reset || !ps) waits<=0;
 else if (!pe) begin waits<=0; target_wait<=transfers%5; end
 else waits<=waits+1;
 if (!reset && ps && pe && prdy) begin
   transfers=transfers+1;
   if (pw) begin
     if (strb!==4'hf) begin $display("FAIL write strobe"); errors=errors+1; end
     memory[pa[9:2]]=pd;
   end
 end
end
task transfer;
 input write_en;
 input [31:0] address, value;
 reg [31:0] expected;
 integer n;
 begin
   @(negedge hc);
   before_count=transfers;
   expected=write_en ? value : memory[address[9:2]];
   ha=address; hw=write_en; ht=2'b10; hd=32'hdeadbeef;
   @(negedge hc);
   if (ready!==0) begin $display("FAIL missing AHB wait"); errors=errors+1; end
   ht=0; hd=value;
   n=0;
   while (!ready && n<300) begin @(negedge hc); n=n+1; end
   if (!ready || resp || transfers!=before_count+1) begin
     $display("FAIL handshake addr=%h count=%d cycles=%d",address,transfers-before_count,n);
     errors=errors+1;
   end
   if ((!write_en && hr!==expected) || (write_en && memory[address[9:2]]!==expected)) begin
     $display("FAIL data addr=%h expect=%h got=%h", address,expected,write_en?memory[address[9:2]]:hr);
     errors=errors+1;
   end
 end
endtask
initial begin
 for(i=0;i<256;i=i+1) memory[i]=32'h12345678^i;
 #40; reset=0;
 for(i=0;i<100;i=i+1) begin transfer(1,i*4,32'h76543210^i); transfer(0,i*4,0); end
 half_sys=50; // HSI 10MHz, APB still 100MHz: old completion pulses can be lost.
 for(i=0;i<100;i=i+1) begin transfer(1,i*4,32'h89abcdef^i); transfer(0,i*4,0); end
 half_sys=2.5;
 fork
   begin #23; half_sys=50; end
   transfer(0,32'h20,0);
 join
 #300;
 if(errors!=0 || transfers!=401) $fatal(1,"FAIL errors=%d transfers=%d",errors,transfers);
 $display("PASS AHB/APB: 401 transfers, APB wait states, write data phase, SYS200/10 and in-flight clock change");
 $finish;
end
initial begin #1000000; $fatal(1,"global simulation timeout"); end
endmodule
