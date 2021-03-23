from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream
from mfcc.misc.mul import *


class PowerSpectrumCalc(Elaboratable):
    def __init__(self, width=16,  multiplier_cls=Multiplier):
        self.i = stream.Endpoint([("r", signed(width)), ("i", signed(width))])
        self.o = stream.Endpoint([("r", 2 * width)])

        self.mul_r = multiplier_cls(signed(width), signed(width))
        self.mul_i = multiplier_cls(signed(width), signed(width))

    def elaborate(self, platform):
        m = Module()
        m.submodules.mul_i = mul_i = self.mul_i
        m.submodules.mul_r = mul_r = self.mul_r

        m.d.comb += [
            self.i.ready.eq(mul_r.i.ready & mul_i.i.ready),

            mul_r.i.a.eq(self.i.r),
            mul_r.i.b.eq(self.i.r),
            mul_r.i.valid.eq(self.i.valid),
            mul_r.i.last.eq(self.i.last),

            mul_i.i.a.eq(self.i.i),
            mul_i.i.b.eq(self.i.i),
            mul_i.i.valid.eq(self.i.valid),

            self.o.r.eq(mul_r.o.c + mul_i.o.c),
            self.o.valid.eq(mul_r.o.valid & mul_i.o.valid),
            self.o.last.eq(mul_r.o.last),

            mul_r.o.ready.eq(self.o.ready),
            mul_i.o.ready.eq(self.o.ready),
        ]

        return m


class PowerSpectrum(Elaboratable):
    def __init__(self, width=16, width_output=24, multiplier_cls=Multiplier):
        self.sink   = stream.Endpoint([("data_r", signed(width)), ("data_i", signed(width))])
        self.source = stream.Endpoint([("data", width_output)])

        self.pow2 = PowerSpectrumCalc(width=width, multiplier_cls=multiplier_cls)
        self.width_output = width_output
        self.width = width

    def elaborate(self, platform):
        m = Module()

        m.submodules.pow2 = pow2 = self.pow2

        m.d.comb += [
            pow2.i.r.eq(self.sink.data_r),
            pow2.i.i.eq(self.sink.data_i),
            pow2.i.valid.eq(self.sink.valid),
            self.sink.ready.eq(pow2.i.ready),
            pow2.i.last.eq(self.sink.last),

            self.source.data.eq(pow2.o.r[-self.width_output:]),
            self.source.valid.eq(pow2.o.valid),
            pow2.o.ready.eq(self.source.ready),
            self.source.last.eq(pow2.o.last),
        ]

        return m


if __name__ == "__main__":
    dut = PowerSpectrum(width=16, multiplier_cls=Multiplier)
    def bench():
        yield dut.sink.data_r.eq(65535)
        yield dut.sink.data_i.eq(65535)
        yield dut.sink.valid.eq(1)
        yield dut.source.ready.eq(0)
        yield

        for j in range(10):
            for i in range(40):
                yield
            yield dut.source.ready.eq(1)
            yield
            yield dut.source.ready.eq(0)
            yield
            if j == 5:
                yield dut.sink.last.eq(1)
            else:
                yield dut.sink.last.eq(0)
            print((yield dut.source.data))



    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("power.vcd"):
        sim.run()
