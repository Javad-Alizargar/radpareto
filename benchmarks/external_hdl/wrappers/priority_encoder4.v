// Original RadPareto wrapper around attributed external RTL. Generic functional model, no physical timing.
(* keep_hierarchy = 1 *) module core_priority_encoder4(input clk, input sel, input [6:0] a,b, output [6:0] y);
priority_encoder #(.WIDTH(4), .LSB_HIGH_PRIORITY(0)) dut(.input_unencoded(a[3:0]), .output_valid(y[4]), .output_encoded(y[6:5]), .output_unencoded(y[3:0]));
endmodule
module base(input clk, input sel, input [6:0] a,b, output [6:0] y); core_priority_encoder4 dut(clk,sel,a,b,y); endmodule
module tmr(input clk, input sel, input [6:0] a,b, output [6:0] y);
wire [6:0] y0,y1,y2;
(* keep = 1, keep_hierarchy = 1 *) core_priority_encoder4 replica0(clk,sel,a,b,y0);
(* keep = 1, keep_hierarchy = 1 *) core_priority_encoder4 replica1(clk,sel,a,b,y1);
(* keep = 1, keep_hierarchy = 1 *) core_priority_encoder4 replica2(clk,sel,a,b,y2);
assign y = (y0 & y1) | (y0 & y2) | (y1 & y2);
endmodule
module check(input clk, input sel, input [6:0] a,b, output ok);
wire [6:0] ref_y, tmr_y;
base refdut(clk,sel,a,b,ref_y); tmr testdut(clk,sel,a,b,tmr_y);
assign ok = ref_y == tmr_y;
endmodule
