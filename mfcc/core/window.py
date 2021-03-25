from nmigen import *
from nmigen.sim import *
from mfcc.misc import stream
from mfcc.misc.mul import *

import numpy as np
from scipy.signal import get_window


class WindowHamming(Elaboratable):
    def __init__(self, width=16, nfft=512, precision=8, multiplier_cls=Multiplier):
        self.width = width
        assert(nfft >= 8)
        self.nfft = nfft
        self.precision = precision

        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])

        self.mul = multiplier_cls(signed(width), precision + 1)

    def calc_coeffs(self):
        maxheight = 2**(self.precision + 1) - 1
        window = get_window("hamm", self.nfft, fftbins=True)
        winfull = (window * maxheight).astype(int)

        # we store only the first quarter of the window values because
        #  the curve can be reconstructed with symetries.
        # also we discard half of the remaining values and reconstruct
        #  the missing ones with linear interpolation at runtime.
        mem = np.copy(winfull[:self.nfft//4][1::2])

        # subtract the first value to make the memory content
        #  fit within 2**precision bits
        off_fst = int(mem[0])
        mem -= off_fst
        assert(max(mem) < 2**self.precision)

        # last value compensation for rebuilding the curve
        off_lst = int(2 * (winfull[self.nfft//4] - off_fst))

        print("mem.init:", mem)
        return mem, off_fst, off_lst

    def elaborate(self, platform):
        m = Module()
        m.submodules.mul = mul = self.mul

        coeffs, off_fst, off_lst = self.calc_coeffs()
        mem = Memory(depth=len(coeffs), width=self.precision, init=coeffs)
        m.submodules.mem_rp = mem_rp = mem.read_port()

        count = Signal(range(self.nfft))
        count_nxt = Signal.like(count)      # anticipate the next count value
        curve = Signal(self.precision + 1)
        point = Signal.like(curve)
        point_r = Signal.like(point)

        # bit selectors
        bit_msb = count[-1]
        bit_dir = count[-2]
        bit_dir_nxt = count_nxt[-2]
        bits_addr = count[1:-2]
        bits_addr_nxt = count_nxt[1:-2]
        bit_odd = count[0]

        average = ((point + point_r) >> 1)
        consumed = (self.sink.valid & self.sink.ready)

        with m.If(~mul.i.valid | mul.i.ready):
            m.d.comb += self.sink.ready.eq(1)
            m.d.sync += [
                # data path
                mul.i.a.eq(self.sink.data),
                mul.i.b.eq(curve),
                mul.i.valid.eq(self.sink.valid),
                mul.i.first.eq(self.sink.first),
                mul.i.last .eq(self.sink.last),
            ]

        m.d.comb += [
            # ctrl path
            self.source.valid.eq(mul.o.valid),
            self.source.data .eq(mul.o.c[-self.width:]),
            self.source.first.eq(mul.o.first),
            self.source.last .eq(mul.o.last),
            mul.o.ready.eq(self.source.ready),
        ]

        # horizontal symetry:
        #  change the memory direction at every window quarter.
        #  when producing a value, anticipate the next memory address
        #  so the data can be read at the next clock cycle.
        addr = Mux(consumed, bits_addr_nxt, bits_addr)
        with m.If(Mux(consumed, bit_dir_nxt, bit_dir)):
            m.d.comb += mem_rp.addr.eq(~addr)
        with m.Else():
            m.d.comb += mem_rp.addr.eq(addr)

        # vertical symetry:
        #  inverse the memory values on the two central quarters
        with m.If(bit_msb ^ bit_dir):
            m.d.comb += point.eq(off_lst - mem_rp.data)
        with m.Else():
            m.d.comb += point.eq(mem_rp.data)

        # interpolation:
        #  compute the missing (even) points
        with m.If(~bit_odd):
            m.d.comb += curve.eq(off_fst + average)
        with m.Else():
            m.d.comb += curve.eq(off_fst + point)

            with m.If(consumed):
                m.d.sync += point_r.eq(point)

        # input counter
        with m.If(consumed):
            with m.If(self.sink.last):
                m.d.sync += count.eq(0)
            with m.Else():
                m.d.comb += count_nxt.eq(count + 1)
                m.d.sync += count.eq(count_nxt)

        self.curve = curve # for simulator
        return m


if __name__ == "__main__":
    import random
    import matplotlib.pyplot as plt
    from scipy.io import wavfile

    dut = WindowHamming(nfft=512, precision=8)
    sample_rate, audio = wavfile.read("f2bjrop1.0.wav")

    data_in = [int(a) for a in audio[2000:2000+dut.nfft]]
    curve = []
    data_out = []

    def sender():
        speed = 1

        i = 0
        while i < len(data_in):
            yield dut.sink.data.eq(data_in[i])
            yield dut.sink.last.eq(i == len(data_in)-1)

            if (not (yield dut.sink.valid) or ((yield dut.sink.valid) and (yield dut.sink.ready))) and (random.random() < speed):
                yield dut.sink.valid.eq(1)

            yield

            if (yield dut.sink.valid) and (yield dut.sink.ready):
                curve.append((yield dut.curve))
                i += 1
                yield dut.sink.valid.eq(0)

    def receiver():
        speed = 1

        yield Passive()
        while True:
            yield dut.source.ready.eq((yield dut.source.valid) and (random.random() < speed))

            yield

            if (yield dut.source.valid) and (yield dut.source.ready):
                data_out.append((yield dut.source.data))

    def bench():
        while len(data_out) < len(data_in):
            yield

        maxheight = 2**(dut.precision + 1) - 1
        window = get_window("hamm", dut.nfft, fftbins=True)

        plt.plot(window * maxheight)
        plt.plot(curve)
        plt.plot(data_in)
        plt.plot(data_out)
        print("curve:", curve)
        plt.show()

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(sender)
    sim.add_sync_process(receiver)
    sim.add_sync_process(bench)
    with sim.write_vcd("window.vcd"):
        sim.run()
