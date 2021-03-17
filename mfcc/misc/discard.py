from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream

class Discard(Elaboratable):
    def __init__(self, width=16, first=0, count=16):
        self.width = width
        self.first = first
        self.count = count
        self.last = first + count - 1

        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()

        inc = Signal()
        index = Signal(range(self.first + self.count + 1))

        consumed = sink.valid & sink.ready
        produced = source.valid & source.ready

        with m.If(sink.valid):

            # Drop the values at the beginning of the input stream
            with m.If(index < self.first):
                m.d.comb += [
                    sink.ready.eq(1),
                    inc.eq(1),
                ]

            # Drop the values at the end of the input stream
            with m.Elif(index > self.last):
                m.d.comb += sink.ready.eq(1)

            # Pass through
            with m.Else():
                m.d.comb += [
                    sink.connect(source, exclude=["first", "last"]),
                    inc.eq(produced),
                ]

        with m.If(consumed & sink.last):
            m.d.sync += index.eq(0)
        with m.Elif(inc):
            m.d.sync += index.eq(index + 1)

        m.d.comb += [
            source.first.eq(index == self.first),
            source.last.eq((index == self.last) | sink.last),
        ]

        return m

if __name__ == "__main__":
    dut = Discard(first=1, count=12)

    def bench():
        yield dut.source.ready.eq(1)

        for i in range(128):
            yield dut.sink.data.eq(i)
            yield dut.sink.valid.eq(1)
            if ((i+1) % 32) == 0:
                yield dut.sink.last.eq(1)
            else:
                yield dut.sink.last.eq(0)
            yield
            while not (yield dut.sink.ready):
                yield

    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("discard.vcd"):
        sim.run()
