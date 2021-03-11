from nmigen import *
from nmigen.sim import Simulator
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

        self.mul = multiplier_cls(width, precision + 1)

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
        sink = self.sink
        source = self.source

        m = Module()
        m.submodules.mul = mul = self.mul

        coeffs, off_fst, off_lst = self.calc_coeffs()
        mem = Memory(depth=len(coeffs), width=self.precision, init=coeffs)
        m.submodules.mem_rp = mem_rp = mem.read_port()

        busy = Signal()
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
        consumed = (sink.valid & ~busy)
        produced = (source.valid & source.ready)

        m.d.comb += [
            # data path
            mul.i_a.eq(sink.data),
            mul.i_b.eq(curve),
            source.data.eq(mul.o[-self.width:]),

            # ctrl path
            mul.start.eq(consumed),
            sink.ready.eq(produced),
            source.valid.eq(sink.valid & mul.done),
            source.first.eq(sink.first),
            source.last.eq(sink.last),
        ]

        # horizontal symetry:
        #  change the memory direction at every window quarter.
        #  when producing a value, anticipate the next memory address
        #  so the data can be read at the next clock cycle.
        addr = Mux(produced, bits_addr_nxt, bits_addr)
        with m.If(Mux(produced, bit_dir_nxt, bit_dir)):
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

            with m.If(produced):
                m.d.sync += point_r.eq(point)

        # output counter
        with m.If(produced):
            with m.If(source.last):
                m.d.sync += count.eq(0)
            with m.Else():
                m.d.sync += count.eq(count + 1)
                m.d.comb += count_nxt.eq(count + 1)

        # multiplier busy
        with m.If(consumed & ~produced):
            m.d.sync += busy.eq(1)
        with m.Elif(produced):
            m.d.sync += busy.eq(0)

        self.curve = curve # for simulator
        return m

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from scipy.io import wavfile

    dut = WindowHamming(nfft=512, precision=8)
    sample_rate, audio = wavfile.read("f2bjrop1.0.wav")

    def bench():
        idx = 0
        curve = []
        signal = [int(a) for a in audio[2000:2000+dut.nfft]]
        output = []
        yield dut.source.ready.eq(1)

        while not len(output) == len(signal):
            yield dut.sink.data.eq(signal[idx])
            yield dut.sink.valid.eq(1)
            yield
            while not (yield dut.sink.ready):
                yield
            idx += 1
            if (yield dut.source.valid) and (yield dut.source.ready):
                curve.append((yield dut.curve))
                output.append((yield dut.source.data))

        maxheight = 2**(dut.precision + 1) - 1
        window = get_window("hamm", dut.nfft, fftbins=True)

        plt.plot(window * maxheight)
        plt.plot(curve)
        plt.plot(signal)
        plt.plot(output)
        print("curve:", curve)
        plt.show()

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("window.vcd"):
        sim.run()
