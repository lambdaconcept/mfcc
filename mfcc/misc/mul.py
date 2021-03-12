from nmigen import *
from nmigen.sim import Simulator

class MultiplierShifter(Elaboratable):
    def __init__(self, shape_a, shape_b):
        self.i_a = i_a = Signal(shape_a)
        self.i_b = i_b = Signal(shape_b)
        self.o = Signal((i_a.width + i_b.width, i_a.signed or i_b.signed))
        self.start = Signal()
        self.done = Signal()

    def elaborate(self, platform):
        m = Module()
        a = Signal(len(self.i_a) + len(self.i_b))
        b = Signal.like(self.i_b)
        cnt=Signal(range(len(self.i_b)))

        with m.If(self.start | cnt):
            m.d.sync +=  [
                a.eq(Mux(self.start, Cat(0,self.i_a), Cat(0, a))),
                b.eq(Mux(self.start, self.i_b[1:], b[1:])),
                cnt.eq(Mux(self.start, len(self.i_b)-1, cnt -1)),
                self.o.eq(
                    Mux(self.start, Mux(self.i_b[0],self.i_a, 0), Mux(b[0], self.o + a, self.o)))
            ]
        with m.Else():
            m.d.comb += self.done.eq(1)
        return m

class MultiplierDoubleShifter(Elaboratable):
    def __init__(self, shape_a, shape_b):
        self.i_a = i_a = Signal(shape_a)
        self.i_b = i_b = Signal(shape_b)
        self.o = Signal((i_a.width + i_b.width, i_a.signed or i_b.signed))
        self.start = Signal()
        self.done = Signal()

    def elaborate(self, platform):
        m = Module()
        a = Signal(len(self.i_a) + len(self.i_b))
        b = Signal.like(self.i_b)
        cnt=Signal(range(len(self.i_b)))

        with m.If(self.start):
            m.d.sync += [
                cnt.eq((len(self.i_b)-1)//2),
                a.eq(Cat([0,0], self.i_a)),
                b.eq(self.i_b[2:])
            ]
            with m.Switch(self.i_b[:2]):
                with m.Case(0):
                    m.d.sync += self.o.eq(0)
                with m.Case(1):
                    m.d.sync += self.o.eq(self.i_a)
                with m.Case(2):
                    m.d.sync += self.o.eq(Cat(0,self.i_a))
                with m.Case(3):
                    m.d.sync += self.o.eq(self.i_a + Cat(0, self.i_a))
        with m.Elif(cnt):
            m.d.sync += [
                cnt.eq(cnt - 1),
                a.eq(Cat([0,0], a)),
                b.eq(b[2:])
            ]
            with m.Switch(b[:2]):
                with m.Case(1):
                    m.d.sync += self.o.eq(self.o + a)
                with m.Case(2):
                    m.d.sync += self.o.eq(self.o + Cat(0,a))
                with m.Case(3):
                    m.d.sync += self.o.eq(self.o + a + Cat(0, a))
        with m.Else():
            m.d.comb += self.done.eq(1)
        return m

class Multiplier(Elaboratable):
    def __init__(self, shape_a, shape_b):
        self.i_a = i_a = Signal(shape_a)
        self.i_b = i_b = Signal(shape_b)
        self.o = Signal((i_a.width + i_b.width, i_a.signed or i_b.signed))
        self.start = Signal()
        self.done = Signal()

    def elaborate(self, platform):
        m = Module()
        m.d.comb += [
            self.o.eq(self.i_a * self.i_b),
            self.done.eq(1)
        ]
        return m
