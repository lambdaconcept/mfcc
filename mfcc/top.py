from nmigen import *
from nmigen.sim import Simulator, Passive
from mfcc.core.frame import *
from mfcc.core.window import *

class Top(Elaboratable):
    def __init__(self, width=16, nfft=512):
        self.width = width
        self.nfft = nfft

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

        m.d.comb += [
            sink.connect(frame.sink),
            frame.source.connect(window.sink),
            window.source.ready.eq(1), # XXX
        ]

        # for simulator
        self.frame = frame
        self.window = window
        return m

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from scipy.io import wavfile

    dut = Top(nfft=512)
    sample_rate, audio = wavfile.read("f2bjrop1.0.wav")

    frames = []
    windows = []

    def collector_frames():
        src = dut.frame.source
        output = []

        yield Passive()
        while True:
            if (yield src.valid) and (yield src.ready):
                output.append((yield src.data))
                if (yield src.last):
                    frames.append(output)
                    print("new frame!")
                    output = []
            yield

    def collector_windows():
        src = dut.window.source
        output = []

        yield Passive()
        while True:
            if (yield src.valid) and (yield src.ready):
                output.append((yield src.data))
                if (yield src.last):
                    windows.append(output)
                    print("new window!")
                    output = []
            yield

    def bench():
        idx = 0
        signal = [int(a) for a in audio]

        while len(windows) < 6:
            yield dut.sink.data.eq(signal[idx])
            yield dut.sink.valid.eq(1)
            yield

            while not (yield dut.sink.ready):
                yield
            idx += 1

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    sim.add_sync_process(collector_frames)
    sim.add_sync_process(collector_windows)
    with sim.write_vcd("top.vcd"):
        sim.run()

    fig, axs = plt.subplots(2 * len(windows), figsize=(10,10))
    for i in range(len(windows)):
        axs[2*i].plot(frames[i])
        axs[2*i+1].plot(windows[i], color="orange")
    plt.show()
