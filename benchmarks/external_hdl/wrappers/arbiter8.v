// Original RadPareto wrapper around attributed external RTL. Generic functional model, no physical timing.
(* keep_hierarchy = 1 *) module core_arbiter8(input clk, input sel, input [11:0] a,b, output [11:0] y);
arbiter #(.PORTS(8), .ARB_TYPE_ROUND_ROBIN(0), .ARB_BLOCK(0), .ARB_BLOCK_ACK(1), .ARB_LSB_HIGH_PRIORITY(0)) dut(.clk(clk), .rst(sel), .request(a[7:0]), .acknowledge(b[7:0]), .grant(y[7:0]), .grant_valid(y[8]), .grant_encoded(y[11:9]));
endmodule
module base(input clk, input sel, input [11:0] a,b, output [11:0] y); core_arbiter8 dut(clk,sel,a,b,y); endmodule
module tmr(input clk, input sel, input [11:0] a,b, output [11:0] y);
wire [11:0] y0,y1,y2;
(* keep = 1, keep_hierarchy = 1 *) core_arbiter8 replica0(clk,sel,a,b,y0);
(* keep = 1, keep_hierarchy = 1 *) core_arbiter8 replica1(clk,sel,a,b,y1);
(* keep = 1, keep_hierarchy = 1 *) core_arbiter8 replica2(clk,sel,a,b,y2);
assign y = (y0 & y1) | (y0 & y2) | (y1 & y2);
endmodule
module check(input clk, input sel, input [11:0] a,b, output ok);
wire [11:0] ref_y, tmr_y;
base refdut(clk,sel,a,b,ref_y); tmr testdut(clk,sel,a,b,tmr_y);
assign ok = ref_y == tmr_y;
endmodule
