from nmigen import *

class BlinkerKeep(Elaboratable):
    def __init__(self, timeout=int(1e6)):
        self.i = Signal()
        self.o = Signal()
        self.timeout = timeout

    def elaborate(self, platform):
        m = Module()

        counter = Signal(range(self.timeout + 1))

        with m.If(self.i):
            m.d.sync += counter.eq(self.timeout)

        with m.Elif(counter > 0):
            m.d.sync += counter.eq(counter - 1)

        with m.Else():
            m.d.sync += counter.eq(0)

        m.d.comb += self.o.eq(counter > 0)

        return m
