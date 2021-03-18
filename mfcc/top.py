from nmigen import *
from nmigen.lib.cdc import FFSynchronizer, ResetSynchronizer
from nmigen.sim import Simulator, Passive
from mfcc.core.frame import *
from mfcc.core.window import *
from mfcc.core.fft_stream import *
from mfcc.core.dct_stream import *
from mfcc.core.pow2 import *
from mfcc.core.filterbank import *
from mfcc.core.log import *
from mfcc.core.preemph import *
from mfcc.misc.mul import *
from mfcc.misc.discard import *
import mfcc.misc.stream as stream
from mfcc.ft601.phy import *

class MFCC(Elaboratable):
    def __init__(self, width=16, nfft=512, samplerate=16e3,
                 nfilters=16, nceptrums=16):
        self.width = width
        self.nfft = nfft
        self.samplerate = samplerate
        self.nfilters = nfilters
        self.nceptrums = nceptrums

        self.reset = Signal()
        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()

        preemph = Preemph(width=self.width)
        m.submodules.preemph = preemph

        frame = Frame(width=self.width,
                      windowlen=self.nfft,
                      stepsize=self.nfft//3,
                      nfft=self.nfft)
        m.submodules.frame = frame

        window = WindowHamming(width=self.width,
                               nfft=self.nfft,
                               precision=8)
        m.submodules.window = window

        fft_stream = FftStream(width=self.width,
                               nfft=self.nfft)
        m.submodules.fft_stream = fft_stream

        fifo_fft = stream.SyncFIFO(fft_stream.source.description,
                                   self.nfft//2, buffered=True)
        m.submodules.fifo_fft = fifo_fft

        powspec = PowerSpectrum(width=self.width,
                                width_output=30,
                                multiplier_cls=Multiplier) # DoubleShifter) # XXX
        m.submodules.powspec = powspec

        fifo_power = stream.SyncFIFO(powspec.source.description,
                                     4, buffered=True)
        m.submodules.fifo_power = fifo_power

        filterbank = FilterBank(width=powspec.width_output,
                                width_output=16,
                                gain=18,
                                sample_rate=self.samplerate,
                                nfft=self.nfft,
                                ntap=self.nfilters,
                                multiplier_cls=Multiplier) # DoubleShifter) # XXX
        m.submodules.filterbank = filterbank

        fifo_filter = stream.SyncFIFO(filterbank.source.description,
                                      self.nfilters, buffered=True)
        m.submodules.fifo_filter = fifo_filter

        m.submodules.log2 = log2 = Log2Fix(filterbank.width_output, 15, multiplier_cls=Multiplier)

        dct_stream = DCTStream(width=self.width, nfft=self.nfilters)
        m.submodules.dct_stream = dct_stream

        discard = Discard(width=self.width, first=1, count=self.nceptrums)
        m.submodules.discard = discard

        m.d.comb += [
            sink.connect(preemph.sink),
            preemph.source.connect(frame.sink),
            frame.source.connect(window.sink),
            window.source.connect(fft_stream.sink),
            fft_stream.source.connect(fifo_fft.sink),
            fifo_fft.source.connect(powspec.sink),
            powspec.source.connect(fifo_power.sink),
            fifo_power.source.connect(filterbank.sink),
            filterbank.source.connect(fifo_filter.sink),
            fifo_filter.source.connect(log2.sink),
            log2.source.connect(dct_stream.sink),
            dct_stream.source.connect(source),

            # discard.sink
        ]

        # for simulator
        self.frame = frame
        self.window = window
        self.fft_stream = fft_stream
        self.powspec = powspec
        self.filterbank = filterbank
        self.log2 = log2
        self.dct_stream = dct_stream
        self.discard = discard

        m = ResetInserter(self.reset)(m)
        return m

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

        reset = (ft601.source.valid & ft601.source.data[-1])

        with m.If(reset):
            m.d.comb += [
                mfcc.reset.eq(1),
                ft601.source.ready.eq(1),
            ]

        with m.Else():
            m.d.comb += [
                ft601.source.connect(mfcc.sink),
                mfcc.source.connect(ft601.sink),
            ]

        return m

def test():
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from scipy.io import wavfile

    dut = MFCC(nfft=512, nfilters=32)
    sample_rate, audio = wavfile.read("f2bjrop1.0.wav")

    def gen_collector(name, src, list_o, field="data"):
        def collector():
            output = []

            yield Passive()
            while True:
                if (yield src.valid) and (yield src.ready):
                    output.append((yield getattr(src, field)))
                    if (yield src.last):
                        list_o.append(output)
                        print("new {}!".format(name))
                        output = []
                yield; yield Delay()
        return collector

    def bench():
        idx = 0
        signal = [int(a) for a in audio]
        nframes = 3
        yield dut.source.ready.eq(1)

        while len(chain[-1]) < nframes:
            yield dut.sink.data.eq(signal[idx])
            yield dut.sink.valid.eq(1)
            yield; yield Delay()

            while not (yield dut.sink.ready):
                yield; yield Delay()
            idx += 1

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)

    chain = [[] for i in range(8)]

    chain[0] = [audio[i: i + dut.frame.windowlen]
               for i in range(0, len(audio), dut.frame.stepsize)]

    sim.add_sync_process(gen_collector("frame", dut.frame.source, chain[1]))
    sim.add_sync_process(gen_collector("window", dut.window.source, chain[2]))
    sim.add_sync_process(gen_collector("fft", dut.fft_stream.source, chain[3], field="data_r"))
    sim.add_sync_process(gen_collector("power", dut.powspec.source, chain[4]))
    sim.add_sync_process(gen_collector("filter", dut.filterbank.source, chain[5]))
    sim.add_sync_process(gen_collector("log", dut.log2.source, chain[6]))
    sim.add_sync_process(gen_collector("dct", dut.dct_stream.source, chain[7]))
    # sim.add_sync_process(gen_collector("discard", dut.discard.source, chain[8]))

    with sim.write_vcd("top.vcd"):
        sim.run()

    print("window", chain[2])
    print("fft", chain[3])
    print("power", chain[4])
    print("filter", chain[5])
    print("log", chain[6])
    print("dct", chain[7])
    # print("discard", chain[8])

    nplots = len(chain)
    nframes = len(chain[-1])

    for i in range(nframes):
        fig, axs = plt.subplots(nplots, figsize=(10,10))
        colors = list(mcolors.TABLEAU_COLORS)
        for j in range(nplots):
            axs[j].plot(chain[j][i], color=colors[j])
    plt.show()

def build():
    from mfcc.board.platform import SDMUlatorPlatform
    # from nmigen.back import rtlil

    # dut = FFT(size=512, i_width=16, o_width=16, m_width=16)
    # print(rtlil.convert(dut))

    platform = SDMUlatorPlatform()
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
