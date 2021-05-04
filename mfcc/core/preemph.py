from nmigen import *
from nmigen.sim import Simulator
from ..misc import stream


"""
Preemph applies a pre-emphasis coefitient of 1-1/32 = 0,96875
"""
class Preemph(Elaboratable):
    def __init__(self, width=16):
        self.width = width
        self.sink = stream.Endpoint([("data", signed(width))])
        self.source = stream.Endpoint([("data", signed(width))])

    def elaborate(self, platform):
        m = Module()

        odata = Signal(signed(self.width))

        with m.If(self.sink.valid & self.sink.ready):
            m.d.sync += odata.eq(self.sink.data)

        m.d.comb += [
            self.source.data.eq(self.sink.data + (odata >> 5) - odata),
            self.sink.ready.eq(self.source.ready),
            self.source.valid.eq(self.sink.valid),
            self.source.last.eq(self.sink.last)
        ]

        return m


if __name__ == "__main__":
    import numpy as np
    import matplotlib.pyplot as plt
    from scipy.io import wavfile

    dut = Preemph()
    val = []
    res = []

    def bench():
        sample_rate, audio = wavfile.read("f2bjrop1.0.wav")

        yield dut.source.ready.eq(1)
        yield dut.sink.valid.eq(1)
        for i in range(2000):
            #v = int(np.uint16(audio[i+1920-256]))
            v = int(audio[i])
            yield dut.sink.data.eq(v)
            yield dut.sink.last.eq((i%512)==0)
            yield
            val.append(v)
            res.append(np.int16((yield dut.source.data)))
            #print(i, v, np.int16((yield dut.source.data)))
        plt.plot(val)
        plt.plot(res)
        plt.show()
        print(val)
        print(res)

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("preemph.vcd"):
        sim.run()
