from nmigen import *
from nmigen.lib.cdc import FFSynchronizer, ResetSynchronizer

from mfcc.misc.blinker import *
import mfcc.misc.stream as stream
from mfcc.ft601.phy import *


class CRG(Elaboratable):
    def __init__(self):
        self.sync_reset = Signal()

    def elaborate(self, platform):
        m = Module()

        clk100_i   = platform.request("clk100", 0).i
        pll_locked = Signal()
        pll_fb     = Signal()
        pll_125    = Signal()
        pll_200    = Signal()

        m.submodules += Instance("PLLE2_BASE",
            p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

            # VCO @ 1000 MHz
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
            p_CLKFBOUT_MULT=10, p_DIVCLK_DIVIDE=1,
            i_CLKIN1=clk100_i,
            i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

            # 125 MHz
            p_CLKOUT1_DIVIDE=8, p_CLKOUT1_PHASE=0.0,
            o_CLKOUT1=pll_125,

            # 200 MHz
            p_CLKOUT2_DIVIDE=5, p_CLKOUT2_PHASE=0.0,
            o_CLKOUT2=pll_200,
        )

        eos = Signal()
        m.submodules += Instance("STARTUPE2",
            o_EOS=eos,
        )

        # sync @ 125 MHz

        m.domains += ClockDomain("sync")
        m.submodules += Instance("BUFGCE",
            i_I=pll_125, i_CE=eos,
            o_O=ClockSignal("sync"),
        )
        m.submodules += ResetSynchronizer(
            arst=~pll_locked | self.sync_reset, domain="sync",
        )

        # idelay_ref @ 200 MHz

        m.domains += ClockDomain("idelay_ref")
        m.submodules += Instance("BUFGCE",
            i_I=pll_200, i_CE=eos,
            o_O=ClockSignal("idelay_ref"),
        )
        m.submodules += ResetSynchronizer(
            arst=~pll_locked, domain="idelay_ref",
        )

        # ft601 @ 100 MHz

        m.domains += ClockDomain("ft601")
        ft601_clk_i = platform.request("ft601_clk").i
        ft601_rst_o = platform.request("ft601_rst").o

        m.submodules += Instance("BUFGCE",
            i_I=ft601_clk_i, i_CE=eos,
            o_O=ClockSignal("ft601"),
        )
        m.d.comb += ft601_rst_o.eq(ResetSignal("ft601"))

        return m


class Top(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()
        m.submodules.crg = crg = CRG()

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
    from mfcc.board.platform import SDMUlatorPlatform
    # from nmigen.back import rtlil

    # dut = FFT(size=512, i_width=16, o_width=16, m_width=16)
    # print(rtlil.convert(dut))

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

    platform.build(Top(), name="top", build_dir="build")

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: {} build|test".format(sys.argv[0]))
        sys.exit(1)

    if sys.argv[1] == "build":
        build()
    elif sys.argv[1] == "test":
        test()
