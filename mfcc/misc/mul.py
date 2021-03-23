from nmigen import *

from mfcc.misc import stream


__all__ = ["Multiplier"]


class Multiplier(Elaboratable):
    def __init__(self, shape_a, shape_b):
        shape_a = Shape.cast(shape_a)
        shape_b = Shape.cast(shape_b)
        shape_c = Shape(shape_a.width + shape_b.width, shape_a.signed or shape_b.signed)
        self.i = stream.Endpoint([("a", shape_a), ("b", shape_b)])
        self.o = stream.Endpoint([("c", shape_c)])

        self.pipe_stages = 1

    def elaborate(self, platform):
        m = Module()

        with m.If(~self.o.valid | self.o.ready):
            m.d.comb += self.i.ready.eq(1)
            m.d.sync += [
                self.o.c.eq(self.i.a * self.i.b),
                self.o.valid.eq(self.i.valid),
                self.o.first.eq(self.i.first),
                self.o.last .eq(self.i.last),
            ]

        return m
