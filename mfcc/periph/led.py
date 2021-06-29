from nmigen import *
from lambdasoc.periph.base import Peripheral

from ..misc.led import SevenSegController


__all__ = ["SevenSegPeripheral"]


class SevenSegPeripheral(Peripheral, Elaboratable):
    def __init__(self, *, pins=None):
        super().__init__()
        self._pins = pins

        bank = self.csr_bank()
        self._en = bank.csr(1, "rw")
        self._data = bank.csr(4, "rw")

        self._bridge  = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus      = self._bridge.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge = self._bridge

        # csr
        with m.If(self._en.w_stb):
            m.d.sync += self._en.r_data.eq(self._en.w_data)
        with m.If(self._data.w_stb):
            m.d.sync += self._data.r_data.eq(self._data.w_data)

        # ctrl

        m.submodules.ctrl = ctrl = SevenSegController()
        m.d.comb += [
            ctrl.val.eq(self._data.r_data),
            self._pins.sel.o.eq(0),
        ]

        with m.If(self._en.r_data):
            m.d.comb += self._pins.val.eq(ctrl.leds)
        with m.Else():
            m.d.comb += self._pins.val.eq(0)

        return m
