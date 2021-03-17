from nmigen import *
from nmigen.sim import *
from mfcc.misc import stream
from mfcc.misc.fft import FFT

class DCTStream(Elaboratable):
    def __init__(self, width=16, nfft=16):
        self.width = width
        self.nfft = nfft
        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()
        m.submodules.fft = mfft = FFT(size=self.nfft*4,
                                      i_width=self.width,
                                      o_width=self.width,
                                      m_width=self.width)

        cnt_fill = Signal(range(self.nfft*8))
        cnt_empty = Signal(range(self.nfft))
        cnt_nxt = Signal.like(cnt_empty)

        produce = (source.valid & source.ready)
        last = (cnt_empty == self.nfft - 1)
        trig = (cnt_fill[0] ^ cnt_fill[1])

        m.d.comb += [
            mfft.i.addr.eq(Mux(trig, ~cnt_fill[1:], cnt_fill[1:])),
            mfft.i.data.real.eq(Mux(cnt_fill[0], sink.data, 0)),
            mfft.i.data.imag.eq(0),

            mfft.o.addr.eq(Mux(produce, cnt_nxt, cnt_empty)),
            source.data.eq(mfft.o.data.real),
        ]

        with m.FSM() as fsm:
            with m.State("FILL"):
                m.d.comb += [
                    mfft.i.en.eq(sink.valid),
                    sink.ready.eq(cnt_fill[:2] == 3)
                ]

                with m.If(sink.valid):
                    m.d.sync += cnt_fill.eq(cnt_fill + 1)
                    with m.If(sink.last & sink.ready):
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

    data_in = [0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861]
    data_out = []
    N = len(data_in)
    dut = DCTStream(nfft=N)

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

        yield Passive()
        while True:
            yield dut.source.ready.eq((yield dut.source.valid) and (random.random() < speed))

            yield

            if (yield dut.source.valid) and (yield dut.source.ready):
                data_out.append((yield dut.source.data))

    def bench():
        while len(data_out) < len(data_in):
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(sender)
    sim.add_sync_process(receiver)
    sim.add_sync_process(bench)
    with sim.write_vcd("dct.vcd"):
        sim.run()

    print("DCT core:")
    dout_core = list(map(np.int16, data_out))
    plt.plot(dout_core)
    print(dout_core)
    print()

    print("DCT scipy:")
    tst = list(map(np.int16, data_in))
    # print(dct(tst, norm="ortho"))
    dout_scipy = dct(tst) // 64
    plt.plot(dout_scipy)
    print(dout_scipy)
    print()

    plt.show()
