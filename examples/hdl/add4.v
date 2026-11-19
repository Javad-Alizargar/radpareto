// Original RadPareto benchmark. Generic functional model, no physical timing.
(* keep_hierarchy = 1 *) module core_add4(input clk, input sel, input [3:0] a,b, output [3:0] y);
assign y = a + b;
endmodule
module base(input clk, input sel, input [3:0] a,b, output [3:0] y); core_add4 dut(clk,sel,a,b,y); endmodule
module tmr(input clk, input sel, input [3:0] a,b, output [3:0] y);
wire [3:0] y0,y1,y2;
(* keep = 1, keep_hierarchy = 1 *) core_add4 replica0(clk,sel,a,b,y0);
(* keep = 1, keep_hierarchy = 1 *) core_add4 replica1(clk,sel,a,b,y1);
(* keep = 1, keep_hierarchy = 1 *) core_add4 replica2(clk,sel,a,b,y2);
assign y = (y0 & y1) | (y0 & y2) | (y1 & y2);
endmodule
module check(input clk, input sel, input [3:0] a,b, output ok);
wire [3:0] ref_y, tmr_y;
base refdut(clk,sel,a,b,ref_y); tmr testdut(clk,sel,a,b,tmr_y);
assign ok = ref_y == tmr_y;
endmodule
