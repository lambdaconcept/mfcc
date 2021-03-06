from nmigen import *
from nmigen.sim import *
from mfcc.misc import stream
from mfcc.misc.fft import FFT

class FftStream(Elaboratable):
    def __init__(self, width=16, nfft=512):
        self.width = width
        self.nfft = nfft
        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data_r", (width, True)), ("data_i", (width, True))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()
        m.submodules.fft = mfft = FFT(size=self.nfft,
                                      i_width=self.width,
                                      o_width=self.width,
                                      m_width=self.width)

        cnt_fill = Signal(range(self.nfft))
        cnt_empty = Signal(range(self.nfft//2))
        cnt_nxt = Signal.like(cnt_empty)

        produce = (source.valid & source.ready)
        last = (cnt_empty == self.nfft//2 - 1)

        m.d.comb += [
            mfft.i.addr.eq(cnt_fill),
            mfft.i.data.real.eq(sink.data),
            mfft.i.data.imag.eq(0),

            mfft.o.addr.eq(Mux(produce, cnt_nxt, cnt_empty)),
            source.data_r.eq(mfft.o.data.real),
            source.data_i.eq(mfft.o.data.imag),
        ]

        with m.FSM() as fsm:
            with m.State("FILL"):
                m.d.comb += [
                    mfft.i.en.eq(sink.valid),
                    sink.ready.eq(1)
                ]

                with m.If(sink.valid):
                    m.d.sync += cnt_fill.eq(cnt_fill + 1)
                    with m.If(sink.last):
                        m.d.comb += mfft.start.eq(1)
                        m.next = "WORK"

            with m.State("WORK"):
                with m.If(mfft.ready):
                    m.d.comb += cnt_nxt.eq(0)
                    m.d.sync += cnt_empty.eq(0)
                    m.next = "EMPTY"

            with m.State("EMPTY"):
                m.d.comb += [
                    source.valid.eq(1),
                    source.last.eq(last),
                ]

                with m.If(source.ready):
                    m.d.comb += cnt_nxt.eq(cnt_empty + 1)
                    m.d.sync += cnt_empty.eq(cnt_nxt)

                    with m.If(last):
                        m.d.sync += cnt_fill.eq(0)
                        m.next = "FILL"

        return m

if __name__ == "__main__":
    import random
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.fftpack import *

    dut = FftStream()
    data_in = [0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc001, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x3fff, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6]
    data_out = []

    def sender():
        speed = 0.25

        i = 0
        while i < len(data_in):
            yield dut.sink.data.eq(data_in[i])
            yield dut.sink.last.eq(i == len(data_in)-1)

            if not (yield dut.sink.valid) and (random.random() < speed):
                yield dut.sink.valid.eq(1)

            yield

            if (yield dut.sink.valid) and (yield dut.sink.ready):
                i += 1
                yield dut.sink.valid.eq(0)

    def receiver():
        speed = 0.25
        p = 0

        yield Passive()
        while True:
            yield dut.source.ready.eq((yield dut.source.valid) and (random.random() < speed))

            yield

            if (yield dut.source.valid) and (yield dut.source.ready):
                data_out.append((yield dut.source.data_r))
                print(p, (yield dut.source.data_r))
                p += 1

    def bench():
        while len(data_out) < (len(data_in) // 2):
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(sender)
    sim.add_sync_process(receiver)
    sim.add_sync_process(bench)
    with sim.write_vcd("fft.vcd"):
        sim.run()

    print("FFT core:")
    dout_core = list(map(np.int16, data_out))
    plt.plot(dout_core)
    print(dout_core)
    print()

    print("FFT scipy:")
    tst = list(map(np.int16, data_in))
    # print(fft(tst, norm="ortho"))
    dout_scipy = fft(tst) // 64
    plt.plot(dout_scipy)
    print(dout_scipy)
    print()

    plt.show()
