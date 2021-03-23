import math
from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream
from mfcc.misc.mul import *


class Log2FixCalc(Elaboratable):
    def __init__(self, width, precision, multiplier_cls=Multiplier, allow_fraction_input=False):
        self.i = stream.Endpoint([("data", width)])
        self.o = stream.Endpoint([("data", width)])

        self.width = width
        self.precision = precision
        self.mul = multiplier_cls(self.precision + 1, self.precision + 1)

        self.allow_fraction_input = allow_fraction_input

    def elaborate(self, platform):
        m = Module()

        mul_rst = Signal()
        m.submodules.mul = mul = ResetInserter(mul_rst)(self.mul)

        b   = Signal(self.width)
        x   = Signal(self.width)
        cnt = Signal(range(self.precision))
        z   = Signal(self.width*2)

        last = Signal()

        with m.FSM():
            with m.State("START"):
                m.d.comb += self.i.ready.eq(1)
                with m.If(self.i.valid):
                    m.d.sync += last.eq(self.i.last)
                    m.d.sync += [
                        b.eq(1 << (self.precision - 1)),
                        self.o.data.eq(0),
                        x.eq(self.i.data),
                    ]
                    if self.allow_fraction_input:
                        m.next = "SHIFT-LEFT"
                    else:
                        m.next = "SHIFT-RIGHT"

            if self.allow_fraction_input:
                with m.State("SHIFT-LEFT"):
                    with m.If(x < (1 << self.precision)):
                        m.d.sync += [
                            x.eq(Cat(Const(0, 1), x)),
                            self.o.data.eq(self.o.data - (1 << self.precision)),
                        ]
                    with m.Else():
                        m.next = "SHIFT-RIGHT"

            with m.State("SHIFT-RIGHT"):
                with m.If(x[self.precision + 1:].any()):
                    m.d.sync += [
                        x.eq(x[1:]),
                        self.o.data.eq(self.o.data + (1 << self.precision)),
                        z.eq(x[1:]),
                    ]
                with m.Else():
                    m.d.sync += cnt.eq(self.precision - 1)
                    m.next = "CALC-1"

            with m.State("CALC-1"):
                m.d.comb += [
                    mul.i.valid.eq(1),
                    mul.i.a.eq(z),
                    mul.i.b.eq(z),
                ]
                with m.If(mul.i.ready):
                    m.next = "CALC-2"

            with m.State("CALC-2"):
                with m.If(cnt == 0):
                    m.d.comb += [
                        self.o.valid.eq(1),
                        self.o.last .eq(last),
                    ]
                    with m.If(self.o.ready):
                        m.d.comb += mul_rst.eq(1)
                        m.next = "START"
                with m.Else():
                    m.d.comb += mul.o.ready.eq(1),
                    with m.If(mul.o.valid):
                        with m.If(mul.o.c[2 * self.precision + 1]):
                            m.d.sync += [
                                z.eq(mul.o.c[self.precision + 1:]),
                                self.o.data.eq(self.o.data + b),
                            ]
                        with m.Else():
                            m.d.sync += z.eq(mul.o.c[self.precision:])
                        m.d.sync += [
                            cnt.eq(cnt - 1),
                            b  .eq(b[1:]),
                        ]
                        m.next = "CALC-1"

            return m


class Log2Fix(Elaboratable):
    def __init__(self, width, width_output, multiplier_cls=Multiplier):
        self.sink   = stream.Endpoint([("data", width)])
        self.source = stream.Endpoint([("data", width_output)])

        self.width = width
        self.width_output = width_output
        self.precision = width_output - math.ceil(math.log2(width))

        self.log2 = Log2FixCalc(width=width + self.precision, precision=self.precision, multiplier_cls=multiplier_cls)

    def elaborate(self, platform):
        m = Module()

        m.submodules.log2 = log2 = self.log2

        with m.If(self.sink.data == 0):
            m.d.comb += log2.i.data.eq(Cat(Const(0, self.precision), Const(1)))
        with m.Else():
            m.d.comb += log2.i.data.eq(Cat(Const(0, self.precision), self.sink.data))

        m.d.comb += [
            log2.i.valid.eq(self.sink.valid),
            self.sink.ready.eq(log2.i.ready),
            log2.i.last.eq(self.sink.last),

            self.source.data.eq(log2.o.data[:self.width_output]),
            self.source.valid.eq(log2.o.valid),
            log2.o.ready.eq(self.source.ready),
            self.source.last.eq(log2.o.last),
        ]

        return m


if __name__ == "__main__":
    dut = Log2Fix(37, 20, multiplier_cls=Multiplier)

    def bench():
        yield dut.sink.data.eq(2207315)
        yield dut.sink.valid.eq(1)
        while not (yield dut.sink.ready):
            yield
        yield
        yield dut.sink.valid.eq(0)
        yield dut.source.ready.eq(1)
        yield
        while not (yield dut.source.valid):
            yield
        print((yield dut.source.data) / (1 << dut.precision))

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("log2.vcd"):
        sim.run()
