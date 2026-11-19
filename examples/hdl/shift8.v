// Original RadPareto benchmark. Generic functional model, no physical timing.
(* keep_hierarchy = 1 *) module core_shift8(input clk, input sel, input [7:0] a,b, output [7:0] y);
reg [7:0] q = 0; always @(posedge clk) q <= {q[6:0],a[0]}; assign y = q;
endmodule
module base(input clk, input sel, input [7:0] a,b, output [7:0] y); core_shift8 dut(clk,sel,a,b,y); endmodule
module tmr(input clk, input sel, input [7:0] a,b, output [7:0] y);
wire [7:0] y0,y1,y2;
(* keep = 1, keep_hierarchy = 1 *) core_shift8 replica0(clk,sel,a,b,y0);
(* keep = 1, keep_hierarchy = 1 *) core_shift8 replica1(clk,sel,a,b,y1);
(* keep = 1, keep_hierarchy = 1 *) core_shift8 replica2(clk,sel,a,b,y2);
assign y = (y0 & y1) | (y0 & y2) | (y1 & y2);
endmodule
module check(input clk, input sel, input [7:0] a,b, output ok);
wire [7:0] ref_y, tmr_y;
base refdut(clk,sel,a,b,ref_y); tmr testdut(clk,sel,a,b,tmr_y);
assign ok = ref_y == tmr_y;
endmodule
