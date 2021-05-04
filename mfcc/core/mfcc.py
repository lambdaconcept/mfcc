from nmigen import *
from nmigen.sim import Simulator, Passive

from .frame import *
from .window import *
from .fft_stream import *
from .dct_stream import *
from .pow2 import *
from .filterbank import *
from .log import *
from .preemph import *
from ..misc.mul import *
# from ..misc.discard import *


__all__ = ["MFCC"]


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

        # discard = Discard(width=self.width, first=1, count=self.nceptrums)
        # m.submodules.discard = discard

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
        # self.discard = discard

        m = ResetInserter(self.reset)(m)
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
        nframes = 3 # (len(audio) - dut.frame.nfft) // dut.frame.stepsize + 1 + 1
        yield dut.source.ready.eq(1)

        while len(chain[-1]) < nframes:
            if idx < len(signal):
                yield dut.sink.data.eq(signal[idx])
            else:
                yield dut.sink.data.eq(0) # padding
            yield dut.sink.valid.eq(1)
            yield; yield Delay()

            while not (yield dut.sink.ready):
                yield; yield Delay()
            idx += 1

        yield dut.sink.valid.eq(0)
        yield dut.reset.eq(1)
        yield
        yield dut.reset.eq(0)
        yield

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


if __name__ == "__main__":
    test()
