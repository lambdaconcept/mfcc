from nmigen import *
from ..misc import stream


__all__ = ["AudioReceiver"]


class AudioReceiver(Elaboratable):
    def __init__(self, clk_freq, sample_freq, i2s_pins=None):
        self.source = stream.Endpoint([("data", 16)])
        self.i2s_in = Record([
            ("da", 1),
            ("ck", 1),
            ("lr", 1),
            ("ws", 1),
        ])

        self.clk_freq     = clk_freq
        self.sample_freq  = sample_freq
        self._i2s_pins    = i2s_pins

    def elaborate(self, platform):
        m = Module()

        if self._i2s_pins is not None:
            m.d.comb += [
                self.i2s_in.da.eq(self._i2s_pins.da.i),
                self._i2s_pins.ck.o.eq(self.i2s_in.ck),
                self._i2s_pins.lr.o.eq(self.i2s_in.lr),
                self._i2s_pins.ws.o.eq(self.i2s_in.ws),
            ]

        tuning_word = Const(int((2 * 2 * 32 * self.sample_freq / self.clk_freq) * 2**32), 32)
        clk_div = Signal(32)
        clk_en  = Signal()
        m.d.sync += Cat(clk_div, clk_en).eq(clk_div + tuning_word)

        ws_ctr = Signal(7)
        with m.If(clk_en):
            m.d.sync += ws_ctr.eq(ws_ctr + 1)

        m.d.comb += [
            self.i2s_in.ws.eq(ws_ctr[6]),
            self.i2s_in.lr.eq(0),
            self.i2s_in.ck.eq(ws_ctr[0]),
        ]

        da_shreg = Signal(32, reset_less=True)
        da_ctr   = Signal(5,  reset=31)

        with m.If(self.source.valid):
            m.d.sync += self.source.valid.eq(0)

        ws_r = Signal()

        with m.If(clk_en & ~self.i2s_in.ck): # rising edge
            m.d.sync += ws_r.eq(self.i2s_in.ws)
            with m.If(~ws_r):
                m.d.sync += da_shreg.eq(Cat(self.i2s_in.da, da_shreg))
                with m.If(da_ctr == 0):
                    m.d.sync += [
                        self.source.data.eq(da_shreg[-22:-6]),
                        self.source.valid.eq(1),
                        da_ctr.eq(da_ctr.reset),
                    ]
                with m.Else():
                    m.d.sync += da_ctr.eq(da_ctr - 1)

        return m


# class Top(Elaboratable):
#     def elaborate(self, platform):
#         m = Module()

#         # i2s_pins = platform.request("i2s_in", 0)
#         # m.submodules.mic = mic = AudioReceiver(clk_freq=100e6, sample_freq=16e3, i2s_pins=i2s_pins)

#         serial_pins = platform.request("uart", 0)
#         # m.submodules.serial = serial = AsyncSerial(divisor=int(100e6 / 1e6), parity="even", pins=serial_pins)
#         m.submodules.serial = serial = AsyncSerial(divisor=int(100e6 / 115200), parity="odd", pins=serial_pins)
#         m.d.comb += [
#             serial.tx.ack.eq(1),
#             serial.tx.data.eq(ord('A')),
#         ]

#         # m.d.sync += serial.tx.ack.eq(serial.tx.rdy),

#         # tx_ack_nxt  = Signal()
#         # tx_data_nxt = Signal(8)
#         # with m.If(mic.source.valid):
#         #     m.d.sync += [
#         #         Cat(tx_data_nxt, serial.tx.data).eq(mic.source.data),
#         #         tx_ack_nxt.eq(1),
#         #         serial.tx.ack.eq(1),
#         #     ]

#         # with m.If(serial.tx.rdy & serial.tx.ack):
#         #     with m.If(tx_ack_nxt):
#         #         m.d.sync += [
#         #             serial.tx.data.eq(tx_data_nxt),
#         #             tx_ack_nxt.eq(0),
#         #         ]
#         #     with m.Else():
#         #         m.d.sync += serial.tx.ack.eq(0)

#         return m



# from nmigen.sim import *
# from nmigen.build import *
# from nmigen_boards.ecpix5 import *
# from nmigen_boards.arty_a7 import ArtyA7Platform
# from nmigen_boards.resources import *
# from nmigen_stdio.serial import *


# if __name__ == "__main__":
    # dut = AudioReceiver(clk_freq=100e6, sample_freq=16e3)
    # sim = Simulator(dut)

    # def i2s_process():
    #     for i in range(16):
    #         for bit in "11111000000000000000011111111111":
    #             yield dut.i2s_in.da.eq(int(bit))
    #             while not (yield dut.i2s_in.ck):
    #                 yield
    #             while (yield dut.i2s_in.ck):
    #                 yield
    #         for bit in "11111111111111111111111111111111":
    #             yield dut.i2s_in.da.eq(int(bit))
    #             while not (yield dut.i2s_in.ck):
    #                 yield
    #             while (yield dut.i2s_in.ck):
    #                 yield
    #         for bit in "11111010101010101010111111111111":
    #             yield dut.i2s_in.da.eq(int(bit))
    #             while not (yield dut.i2s_in.ck):
    #                 yield
    #             while (yield dut.i2s_in.ck):
    #                 yield
    #         for bit in "11111111111111111111111111111111":
    #             yield dut.i2s_in.da.eq(int(bit))
    #             while not (yield dut.i2s_in.ck):
    #                 yield
    #             while (yield dut.i2s_in.ck):
    #                 yield

    # def out_process():
    #     for i in range(32):
    #         while not (yield dut.source.valid):
    #             yield

    # sim.add_clock(1e-6)
    # sim.add_sync_process(i2s_process)
    # sim.add_sync_process(out_process)
    # with sim.write_vcd("dump.vcd"):
    #     sim.run()

    # platform = ECPIX585Platform()
    # # platform = ArtyA7Platform()
    # # platform = ECPIX545Platform()
    # platform.add_resources([
    #     # Resource("i2s_in", 0,
    #         # Subsignal("da", Pins( "1", dir="i", conn=("pmod", 0))),
    #         # Subsignal("ck", Pins( "2", dir="o", conn=("pmod", 0))),
    #         # Subsignal("lr", Pins( "3", dir="o", conn=("pmod", 0))),
    #         # Subsignal("ws", Pins( "4", dir="o", conn=("pmod", 0))),
    #         # Attrs(IO_TYPE="LVCMOS33"),
    #         # Attrs(IOSTANDARD="LVCMOS33"),
    #     # ),
    #     Resource("pmod", 1,
    #         Subsignal("d0", Pins( "1", dir="o", conn=("pmod", 1))),
    #         Subsignal("d1", Pins( "2", dir="o", conn=("pmod", 1))),
    #         Subsignal("d2", Pins( "3", dir="o", conn=("pmod", 1))),
    #         Subsignal("d3", Pins( "4", dir="o", conn=("pmod", 1))),
    #         Subsignal("d4", Pins( "7", dir="o", conn=("pmod", 1))),
    #         Subsignal("d5", Pins( "8", dir="o", conn=("pmod", 1))),
    #         Subsignal("d6", Pins( "9", dir="o", conn=("pmod", 1))),
    #         Subsignal("d7", Pins("10", dir="o", conn=("pmod", 1))),
    #         Attrs(IO_TYPE="LVCMOS33"),
    #         # Attrs(IOSTANDARD="LVCMOS33"),
    #     ),
    #     UARTResource(1, rx="1", tx="2", conn=("pmod", 0), attrs=Attrs(IO_TYPE="LVCMOS33")),
    # ])
    # platform.build(Top(), do_build=True, do_program=True)
