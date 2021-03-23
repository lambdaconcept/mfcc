from nmigen import *


__all__ = ["Memory1W1R"]


class Memory1W1R(Elaboratable):
    def __init__(self, *, width, depth, init=None, name=None, attrs=None):
        self._storage = Memory(width=width, depth=depth, init=init, name=name, attrs=attrs)

        self.width = self._storage.width
        self.depth = self._storage.depth
        self.attrs = self._storage.attrs
        self.init  = self._storage.init

        self.rp = Record([
            ("addr", range(depth)),
            ("data", width),
        ])
        self.wp = Record([
            ("addr", range(depth)),
            ("en",   1),
            ("data", width),
        ])

    def elaborate(self, platform):
        m = Module()

        m.submodules.storage_rp = storage_rp = self._storage.read_port(transparent=False)
        m.submodules.storage_wp = storage_wp = self._storage.write_port()

        m.d.comb += [
            storage_rp.addr.eq(self.rp.addr),
            storage_rp.en  .eq(Const(1)),

            storage_wp.addr.eq(self.wp.addr),
            storage_wp.en  .eq(self.wp.en),
            storage_wp.data.eq(self.wp.data),
        ]

        collision = Signal()
        data_fwd  = Signal(self.width)
        m.d.sync += [
            collision.eq(self.wp.en & (self.wp.addr == self.rp.addr)),
            data_fwd .eq(self.wp.data),
        ]

        with m.If(collision):
            m.d.comb += self.rp.data.eq(data_fwd)
        with m.Else():
            m.d.comb += self.rp.data.eq(storage_rp.data)

        return m


import unittest
from nmigen.sim import *

class Memory1W1RTestCase(unittest.TestCase):
    def test_simple(self):
        dut = Memory1W1R(width=8, depth=4)
        sim = Simulator(dut)
        sim.add_clock(1e-6)

        def process():
            yield dut.wp.addr.eq(1)
            yield dut.wp.en  .eq(1)
            yield dut.wp.data.eq(0xa5)
            yield
            yield dut.wp.en  .eq(0)
            yield dut.rp.addr.eq(1)
            yield; yield Delay()
            self.assertEqual((yield dut.rp.data), 0xa5)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()

    def test_collision(self):
        dut = Memory1W1R(width=8, depth=4)
        sim = Simulator(dut)
        sim.add_clock(1e-6)

        def process():
            yield dut.wp.addr.eq(1)
            yield dut.wp.en  .eq(1)
            yield dut.wp.data.eq(0xa5)
            yield dut.rp.addr.eq(1)
            yield; yield Delay()
            yield dut.wp.data.eq(0xb6)
            self.assertEqual((yield dut.rp.data), 0xa5)
            yield; yield Delay()
            self.assertEqual((yield dut.rp.data), 0xb6)
            yield dut.wp.en  .eq(0)
            yield; yield Delay()
            self.assertEqual((yield dut.rp.data), 0xb6)

        sim.add_sync_process(process)
        with sim.write_vcd("test.vcd"):
            sim.run()
