from nmigen import *

from ..core.mfcc import MFCC
from ..misc.led import *
from ..io.ft601 import *


__all__ = ["Top"]


class Top(Elaboratable):
    def __init__(self, crg):
        self._crg = crg

    def elaborate(self, platform):
        m = Module()
        m.submodules.crg = self._crg

        m.submodules.mfcc = mfcc = MFCC(nfft=512, nfilters=32, nceptrums=16)
        m.submodules.ft601 = ft601 = FT601PHY(pads=platform.request("ft601", 0))
        m.submodules.blinker_rx = blinker_rx = BlinkerKeep()
        m.submodules.blinker_tx = blinker_tx = BlinkerKeep()

        led_rx = platform.request("led", 0)
        led_tx = platform.request("led", 1)

        reset = (ft601.source.valid & ft601.source.data[-1])

        rx = (ft601.source.valid & ft601.source.ready)
        tx = (ft601.sink.valid & ft601.sink.ready)

        with m.If(reset):
            m.d.comb += [
                mfcc.reset.eq(1),
                ft601.source.ready.eq(1),
            ]

        with m.Else():
            m.d.comb += [
                ft601.source.connect(mfcc.sink),
                mfcc.source.connect(ft601.sink),

                blinker_rx.i.eq(rx),
                blinker_tx.i.eq(tx),
                led_rx.eq(blinker_rx.o),
                led_tx.eq(blinker_tx.o),
            ]

        # LiteScope

        # uart_pins = platform.request("uart", 0)

        # m.submodules.litescope = Instance("litescope",
        #     i_clk=ClockSignal("sync"),
        #     i_rst=ResetSignal("sync"),
        #     o_serial_tx=uart_pins.tx,
        #     i_serial_rx=uart_pins.rx,

        #     i_prb_mfcc_reset=mfcc.reset,

        #     i_prb_mfcc_sink_valid=mfcc.sink.valid,
        #     i_prb_mfcc_sink_ready=mfcc.sink.ready,
        #     i_prb_mfcc_sink_data=mfcc.sink.data,

        #     i_prb_mfcc_source_valid=mfcc.source.valid,
        #     i_prb_mfcc_source_ready=mfcc.source.ready,
        #     i_prb_mfcc_source_data=mfcc.source.data,
        # )

        return m


def build():
    from ..board.sdmulator import SDMUlatorPlatform, SDMUlatorCRG
    platform = SDMUlatorPlatform()

    # from nmigen.build.dsl import Attrs
    # from nmigen_boards.resources import UARTResource
    # platform.add_resources([
    #     UARTResource(0,
    #         rx="1", tx="2", conn=("cn", 14),
    #         attrs=Attrs(IOSTANDARD="LVCMOS33")
    #     ),
    # ])
    # with open("litescope.v", "r")  as f:
    #     platform.add_file("litescope.v", f)

    top = Top(SDMUlatorCRG())
    platform.build(top, name="top", build_dir="build")


if __name__ == "__main__":
    build()
