/*
* Copyright (C) 2020  The SymbiFlow Authors.
*
*  Use of this source code is governed by a ISC-style
*  license that can be found in the LICENSE file or at
*  https://opensource.org/licenses/ISC
*
*  SPDX-License-Identifier: ISC
*/

/*
 * Generated by harness_gen.py
 * From: VexRiscv.v
 */
module top(
    input  wire clk, 
    input  wire stb, 
    input  wire di, 
    output wire do
);

    localparam integer DIN_N = 134;
    localparam integer DOUT_N = 148;

    reg [DIN_N-1:0] din;
    wire [DOUT_N-1:0] dout;

    reg [DIN_N-1:0] din_shr;
    reg [DOUT_N-1:0] dout_shr;

    always @(posedge clk) begin
        din_shr <= {din_shr, di};
        dout_shr <= {dout_shr, din_shr[DIN_N-1]};
        if (stb) begin
            din <= din_shr;
            dout_shr <= dout;
        end
    end

    assign do = dout_shr[DOUT_N-1];
    VexRiscv dut(
            .externalResetVector(din[31:0]),
            .timerInterrupt(din[32]),
            .externalInterruptArray(din[64:33]),
            .iBusWishbone_CYC(dout[0]),
            .iBusWishbone_STB(dout[1]),
            .iBusWishbone_ACK(din[65]),
            .iBusWishbone_WE(dout[2]),
            .iBusWishbone_ADR(dout[32:3]),
            .iBusWishbone_DAT_MISO(din[97:66]),
            .iBusWishbone_DAT_MOSI(dout[64:33]),
            .iBusWishbone_SEL(dout[68:65]),
            .iBusWishbone_ERR(din[98]),
            .iBusWishbone_BTE(dout[70:69]),
            .iBusWishbone_CTI(dout[73:71]),
            .dBusWishbone_CYC(dout[74]),
            .dBusWishbone_STB(dout[75]),
            .dBusWishbone_ACK(din[99]),
            .dBusWishbone_WE(dout[76]),
            .dBusWishbone_ADR(dout[106:77]),
            .dBusWishbone_DAT_MISO(din[131:100]),
            .dBusWishbone_DAT_MOSI(dout[138:107]),
            .dBusWishbone_SEL(dout[142:139]),
            .dBusWishbone_ERR(din[132]),
            .dBusWishbone_BTE(dout[144:143]),
            .dBusWishbone_CTI(dout[147:145]),
            .clk(clk),
            .reset(din[133])
            );

endmodule
