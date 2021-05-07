from nmigen import *


__all__ = ["BlinkerKeep", "SevenSegController"]


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


class SevenSegController(Elaboratable):
    def __init__(self):
        self.val  = Signal(4)
        self.leds = Signal(7)
 
    def elaborate(self, platform):
        m = Module()
 
        table = Array([
            0b0111111, # 0
            0b0000110, # 1
            0b1011011, # 2
            0b1001111, # 3
            0b1100110, # 4
            0b1101101, # 5
            0b1111101, # 6
            0b0000111, # 7
            0b1111111, # 8
            0b1101111, # 9
            0b1110111, # A
            0b1111100, # B
            0b0111001, # C
            0b1011110, # D
            0b1111001, # E
            0b1110001  # F
        ])
 
        m.d.comb += self.leds.eq(table[self.val])
 
        return m
