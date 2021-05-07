from nmigen import *
from nmigen.sim import Simulator
from . import stream


__all__ = ["MagicInserter"]


class MagicInserter(Elaboratable):
    def __init__(self, width=16, magic=0xa55a):
        self.width = width
        self.magic = magic

        self.sink = stream.Endpoint([("data", signed(width))])
        self.source = stream.Endpoint([("data", signed(width))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()

        with m.FSM() as fsm:

            # Insert a magic value at the beginning of the stream
            # to act as a delimiter
            with m.State("MAGIC"):
                m.d.comb += [
                    source.first.eq(1),
                    source.data.eq(self.magic),
                    source.valid.eq(sink.valid),
                ]
                with m.If(source.valid & source.ready):
                    m.next = "FORWARD"

            with m.State("FORWARD"):
                m.d.comb += sink.connect(source, exclude=["first"])
                with m.If(source.valid & source.ready & source.last):
                    m.next = "MAGIC"

        return m


if __name__ == "__main__":
    dut = MagicInserter()

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
    with sim.write_vcd("magic.vcd"):
        sim.run()
