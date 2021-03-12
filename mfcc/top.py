from nmigen import *
from nmigen.sim import Simulator, Passive
from mfcc.core.frame import *
from mfcc.core.window import *
from mfcc.core.fft_stream import *
from mfcc.core.pow2 import *
from mfcc.core.filterbank import *
from mfcc.core.log import *
from mfcc.misc.mul import *
import mfcc.misc.stream as stream

class Top(Elaboratable):
    def __init__(self, width=16, nfft=512, samplerate=16e3, nfilters=26):
        self.width = width
        self.nfft = nfft
        self.samplerate = samplerate
        self.nfilters = nfilters

        self.sink = stream.Endpoint([("data", (width, True))])

    def elaborate(self, platform):
        sink = self.sink

        m = Module()

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

        m.submodules.fifo_fft = fifo_fft = stream.SyncFIFO(fft_stream.source.description, 256)

        powspec = PowerSpectrum(width=self.width,
                                width_output=24,
                                multiplier_cls=Multiplier) # DoubleShifter) # XXX
        m.submodules.powspec = powspec

        m.submodules.fifo_power = fifo_power = stream.SyncFIFO(powspec.source.description, 4)

        filterbank = FilterBank(width=24,
                                width_output=37,
                                width_mul=None,
                                sample_rate=self.samplerate,
                                nfft=self.nfft,
                                ntap=self.nfilters,
                                multiplier_cls=Multiplier) # DoubleShifter) # XXX
        m.submodules.filterbank = filterbank

        m.submodules.fifo_filter = fifo_filter = stream.SyncFIFO(filterbank.source.description, 16)

        m.submodules.log2 = log2 = Log2Fix(37, 12, multiplier_cls=Multiplier)

        m.d.comb += [
            sink.connect(frame.sink),
            frame.source.connect(window.sink),
            window.source.connect(fft_stream.sink),
            fft_stream.source.connect(fifo_fft.sink),
            fifo_fft.source.connect(powspec.sink),
            powspec.source.connect(fifo_power.sink),
            fifo_power.source.connect(filterbank.sink),
            filterbank.source.connect(fifo_filter.sink),
            fifo_filter.source.connect(log2.sink),

            log2.source.ready.eq(1) # XXX
        ]

        # for simulator
        self.frame = frame
        self.window = window
        self.fft_stream = fft_stream
        self.powspec = powspec
        return m

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from scipy.io import wavfile

    dut = Top(nfft=512)
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
                yield
        return collector

    def bench():
        idx = 0
        signal = [int(a) for a in audio]
        nframes = 3

        while len(chain[-1]) < nframes:
            yield dut.sink.data.eq(signal[idx])
            yield dut.sink.valid.eq(1)
            yield

            while not (yield dut.sink.ready):
                yield
            idx += 1

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)

    chain = [[] for i in range(4)]

    sim.add_sync_process(gen_collector("frame", dut.frame.source, chain[0]))
    sim.add_sync_process(gen_collector("window", dut.window.source, chain[1]))
    sim.add_sync_process(gen_collector("fft", dut.fft_stream.source, chain[2], field="data_r"))
    sim.add_sync_process(gen_collector("power", dut.powspec.source, chain[3]))

    with sim.write_vcd("top.vcd"):
        sim.run()

    n = len(chain)
    fig, axs = plt.subplots(n * len(chain[-1]), figsize=(10,10))
    for i in range(len(chain[-1])):
        axs[n*i+0].plot(chain[0][i], color="blue")
        axs[n*i+1].plot(chain[1][i], color="orange")
        axs[n*i+2].plot(chain[2][i], color="green")
        axs[n*i+3].plot(chain[3][i], color="red")
    plt.show()
