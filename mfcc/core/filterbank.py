from nmigen import *
from nmigen.sim import Simulator
import numpy as np
from mfcc.misc import stream
from mfcc.misc.mul import *
import math


def freq_to_mel(freq):
    return 2595.0 * np.log10(1.0 + freq / 700.0)

def met_to_freq(mels):
    return 700.0 * (10.0**(mels / 2595.0) - 1.0)

def get_filter_points(fmin, fmax, mel_filter_num, FFT_size, sample_rate=44100):
    fmin_mel = freq_to_mel(fmin)
    fmax_mel = freq_to_mel(fmax)
    mels = np.linspace(fmin_mel, fmax_mel, num=mel_filter_num+2)
    freqs = met_to_freq(mels)
    return np.floor((FFT_size + 1) / sample_rate * freqs).astype(int)

def calc_filters(tab, wsize=9):
    output = []
    max_acc = 1 << ((2*wsize))
    print(tab)
    for i in range(len(tab)-1):
        diff = tab[i+1] - tab[i] -1
        if(diff):
            step = (max_acc//diff) -1
        else:
            step = max_acc-1
        output.append(step)

    return output


class FilterBank(Elaboratable):
    def __init__(
            self,
            width=24,
            width_output=24,
            width_mul=None,
            gain=0,
            sample_rate=16000,
            nfft=512,
            ntap=16,
            multiplier_cls=Multiplier
    ):
        if width_mul == None:
            self.width_mul = width
        else:
            self.width_mul = width_mul

        self.width = width
        self.nfft = nfft
        self.ntap = ntap
        self.width_output = width_output
        self.gain = gain
        self.mul = multiplier_cls(width, self.width_mul)
        self.sink = stream.Endpoint([("data", width)])
        self.source = stream.Endpoint([("data", width_output)])
        self.points = get_filter_points(0, sample_rate/2, ntap, nfft, sample_rate=sample_rate)
        self.filters = calc_filters(self.points, wsize=self.width_mul)

    def elaborate(self, platform):
        m = Module()
        mem = Memory(depth=len(self.filters), width=2*self.width_mul, init=self.filters)
        m.submodules.mem_rp = mem_rp = mem.read_port(domain="comb")
        m.submodules.mul = mul = self.mul

        maxvalrange = int(math.log2(self.points[-1] - self.points[-3])) + self.width + self.width_mul

        mul_stages = [
            Record([
                ("highest",    1),
                ("data",       self.width),
                ("filter_adr", len(mem_rp.addr)),
            ], name=f"stage_{j}") for j in range(mul.pipe_stages + 1)
        ]

        i_stage = mul_stages[ 0]
        o_stage = mul_stages[-1]

        for i, o in zip(mul_stages, mul_stages[1:]):
            with m.If(mul.i.ready):
                m.d.sync += o.eq(i)

        # Input

        i_acc = Signal(2 * self.width_mul)
        m.d.comb += [
            i_stage.highest.eq(i_acc[self.width_mul:] == ((1 << self.width_mul) - 1)),
            i_stage.data   .eq(self.sink.data),
        ]

        i_stage.filter_adr.reset = 0
        m.d.comb += mem_rp.addr.eq(i_stage.filter_adr)

        m.d.comb += [
            self.sink.ready.eq(mul.i.ready),
            mul.i.valid.eq(self.sink.valid),
            mul.i.a.eq(self.sink.data),
            mul.i.b.eq(i_acc[self.width_mul:]),
            mul.i.last.eq(self.sink.last),
        ]

        with m.If(mul.i.valid & mul.i.ready):
            with m.If(i_stage.highest | mul.i.last):
                with m.If(mul.i.last):
                    m.d.sync += i_stage.filter_adr.eq(0)
                with m.Else():
                    m.d.sync += i_stage.filter_adr.eq(i_stage.filter_adr + 1)
                m.d.sync += i_acc.eq(0)
            with m.Else():
                m.d.sync += i_acc.eq(i_acc + mem_rp.data)

        # Output

        o_rega = Signal(maxvalrange)
        o_regb = Signal(maxvalrange)
        o_data = Signal(self.width_output)
        m.d.comb += o_data.eq(o_regb[-(self.gain + self.width_output):][:self.width_output]),

        with m.If(mul.o.valid & mul.o.ready):
            with m.If(o_stage.highest | mul.o.last):
                m.d.sync += [
                    o_rega.eq(0),
                    o_regb.eq(o_rega + (o_stage.data << self.width_mul)),
                ]
            with m.Else():
                m.d.sync += [
                    o_rega.eq(o_rega + mul.o.c),
                    o_regb.eq(o_regb + (o_stage.data << self.width_mul) - mul.o.c),
                ]

        with m.If(~self.source.valid | self.source.ready):
            m.d.comb += mul.o.ready.eq(1)
            m.d.sync += [
                self.source.valid.eq(mul.o.valid & (o_stage.highest | mul.o.last) & (o_stage.filter_adr != 0)),
                self.source.data .eq(o_data),
                self.source.last .eq(mul.o.last),
            ]

        return m


if __name__ == "__main__":
    dut = FilterBank(width=31, width_output=32, multiplier_cls=Multiplier)

    def w_bench():
        yield dut.sink.data .eq(1234)
        yield dut.sink.valid.eq(1)
        for i in range(600):
            while not (yield dut.sink.ready):
                yield
            yield dut.sink.last.eq(i == 599)
            yield
        yield dut.sink.valid.eq(0)
        yield

    def r_bench():
        yield dut.source.ready.eq(1)
        while True:
            while not (yield dut.source.valid):
                yield
            print((yield dut.source.data))
            if (yield dut.source.last):
                break
            yield

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(w_bench)
    sim.add_sync_process(r_bench)
    with sim.write_vcd("filterbank.vcd"):
        sim.run()
