import numpy as np

from nmigen import *
from nmigen.hdl.rec import Layout
from nmigen.utils import log2_int


__all__ = ["complex", "TwiddleROM", "Butterfly", "Scheduler", "FFT"]


def complex(width):
    return Layout([
        ("real", signed(width)),
        ("imag", signed(width)),
    ])


class TwiddleROM(Elaboratable):
    def __init__(self, size, width, invert=False):
        self.rp_addr = Signal(range(size // 2))
        self.rp_data = Record(complex(width))

        self.size   = size
        self.width  = width
        self.invert = invert
        self._init  = None

    @property
    def init(self):
        if not self._init:
            p = np.linspace(start=0, stop=np.pi / 2, num=int(self.size // 4), endpoint=False)
            self._init = [
                int(x.real) | int(x.imag) << self.width
                for x in np.round((1 << (self.width - 2)) * np.exp(-1j * p))
            ]
        return self._init

    def elaborate(self, platform):
        m = Module()

        mem = Memory(width=2 * self.width, depth=int(self.size // 4), init=self.init)
        m.submodules.mem_rp = mem_rp = mem.read_port()
        m.d.comb += mem_rp.addr.eq(self.rp_addr[:-1])

        mem_rp_sel = Signal()
        m.d.sync += mem_rp_sel.eq(self.rp_addr[-1])

        m.d.comb += self.rp_data.real.eq(mem_rp.data.word_select(mem_rp_sel, self.width))

        if self.invert:
            with m.If(mem_rp_sel):
                m.d.comb += self.rp_data.imag.eq( mem_rp.data.word_select(0, self.width))
            with m.Else():
                m.d.comb += self.rp_data.imag.eq(-mem_rp.data.word_select(1, self.width))
        else:
            with m.If(mem_rp_sel):
                m.d.comb += self.rp_data.imag.eq(-mem_rp.data.word_select(0, self.width))
            with m.Else():
                m.d.comb += self.rp_data.imag.eq( mem_rp.data.word_select(1, self.width))

        return m


class Butterfly(Elaboratable):
    def __init__(self, *, width, bias_width, scale_bit):
        self.reset = Signal()

        self.i = Record([
            ("stb", 1),
            ("tw",  complex(width)),
            ("x0",  complex(width)),
            ("x1",  complex(width)),
        ])
        self.o = Record([
            ("stb", 1),
            ("y0",  complex(width)),
            ("y1",  complex(width)),
        ])

        self.o.y0.real.reset_less = True
        self.o.y0.imag.reset_less = True
        self.o.y1.real.reset_less = True
        self.o.y1.imag.reset_less = True

        self.width      = width
        self.bias_width = bias_width
        self.scale_bit  = scale_bit

    def elaborate(self, platform):
        m = Module()
        m = ResetInserter(self.reset)(m)

        if self.bias_width > 0:
            bias = Const((1 << self.bias_width - 1) - 1, self.bias_width)
        else:
            bias = Const(0)

        s1_stb   = Signal()
        s1_x0    = Record(complex(self.width))
        s1_x1    = Record(complex(self.width))
        s1_tw    = Record(complex(self.width))

        s1_x0.real.reset_less = True
        s1_x0.imag.reset_less = True
        s1_x1.real.reset_less = True
        s1_x1.imag.reset_less = True
        s1_tw.real.reset_less = True
        s1_tw.imag.reset_less = True

        s2_stb   = Signal()
        s2_x0    = Record.like(s1_x0)
        s2_x1    = Record.like(s1_x1)
        s2_tw    = Record.like(s1_tw)
        s2_add_0 = Signal(signed(2 * self.width + 1), reset_less=True)

        s3_stb   = Signal()
        s3_x0    = Record.like(s2_x0)
        s3_x1    = Record.like(s2_x1)
        s3_tw    = Record.like(s2_tw)
        s3_mul_0 = Signal(signed(2 * self.width + 1), reset_less=True)

        s4_stb   = Signal()
        s4_x0    = Record.like(s3_x0)
        s4_x1    = Record.like(s3_x1)
        s4_mul_0 = Signal.like(s3_mul_0)
        s4_add_1 = Signal(signed(2 * self.width + 1), reset_less=True)
        s4_sub_0 = Signal(signed(2 * self.width + 1), reset_less=True)

        s5_stb   = Signal()
        s5_x0    = Record.like(s4_x0)
        s5_mul_0 = Signal.like(s4_mul_0)
        s5_mul_1 = Signal(signed(2 * self.width + 1), reset_less=True)
        s5_mul_2 = Signal(signed(2 * self.width + 1), reset_less=True)

        s6_stb   = Signal()
        s6_x0    = Record.like(s5_x0)
        s6_sub_1 = Signal(signed(2 * self.width + 1), reset_less=True)
        s6_sub_2 = Signal(signed(2 * self.width + 1), reset_less=True)

        m.d.sync += [
            # Stage 1
            s1_stb.eq(self.i.stb),
            s1_x0.eq(self.i.x0),
            s1_x1.eq(self.i.x1),
            s1_tw.eq(self.i.tw),

            # Stage 2
            s2_stb.eq(s1_stb),
            s2_x0.eq(s1_x0),
            s2_x1.eq(s1_x1),
            s2_tw.eq(s1_tw),
            s2_add_0.eq(s1_x1.real + s1_x1.imag), # Re(x₁) + Im(x₁)

            # Stage 3
            s3_stb.eq(s2_stb),
            s3_x0.eq(s2_x0),
            s3_x1.eq(s2_x1),
            s3_tw.eq(s2_tw),
            s3_mul_0.eq(s2_add_0 * s2_tw.real), # Re(x₁)Re(ω) + Im(x₁)Re(ω)

            # Stage 4
            s4_stb.eq(s3_stb),
            s4_x0.eq(s3_x0),
            s4_x1.eq(s3_x1),
            s4_mul_0.eq(s3_mul_0 + bias),
            s4_add_1.eq(s3_tw.real + s3_tw.imag), # Re(ω) + Im(ω)
            s4_sub_0.eq(s3_tw.real - s3_tw.imag), # Re(ω) - Im(ω)

            # Stage 5
            s5_stb.eq(s4_stb),
            s5_x0.eq(s4_x0),
            s5_mul_0.eq(s4_mul_0),
            s5_mul_1.eq(s4_x1.imag * s4_add_1), # Im(x₁)Re(ω) + Im(x₁)Im(ω)
            s5_mul_2.eq(s4_x1.real * s4_sub_0), # Re(x₁)Re(ω) - Re(x₁)Im(ω)

            # Stage 6
            s6_stb.eq(s5_stb),
            s6_x0.eq(s5_x0),
            s6_sub_1.eq(s5_mul_0 - s5_mul_1), # Re(x₁)Re(ω) - Im(x₁)Im(ω)
            s6_sub_2.eq(s5_mul_0 - s5_mul_2), # Im(x₁)Re(ω) + Re(x₁)Im(ω)

            # Stage 7
            self.o.stb.eq(s6_stb),
            # Re(y₀) = Re(x₀) +  Re(x₁)Re(ω) - Im(x₁)Im(ω)
            # Im(y₀) = Im(x₀) +  Im(x₁)Re(ω) + Re(x₁)Im(ω)
            # Re(y₁) = Re(x₀) - (Re(x₁)Re(ω) - Im(x₁)Im(ω))
            # Im(y₁) = Im(x₀) - (Im(x₁)Re(ω) + Re(x₁)Im(ω))
            self.o.y0.real.eq((s6_x0.real + s6_sub_1[self.bias_width:])[self.scale_bit:]),
            self.o.y0.imag.eq((s6_x0.imag + s6_sub_2[self.bias_width:])[self.scale_bit:]),
            self.o.y1.real.eq((s6_x0.real - s6_sub_1[self.bias_width:])[self.scale_bit:]),
            self.o.y1.imag.eq((s6_x0.imag - s6_sub_2[self.bias_width:])[self.scale_bit:]),
        ]

        return m


class Scheduler(Elaboratable):
    def __init__(self, *, size, width):
        self.start = Signal()
        self.done  = Signal()

        self.i = Record([
            ("stb", 1),
            ("y0",  complex(width)),
            ("y1",  complex(width)),
        ])
        self.o = Record([
            ("stb", 1),
            ("tw",   complex(width)),
            ("x0",  complex(width)),
            ("x1",  complex(width)),
        ])

        def memory_port(depth, width, mode):
            fields = []
            if "r" in mode:
                fields.append(("rp", [
                    ("addr", range(depth)),
                    ("data", complex(width)),
                ]))
            if "w" in mode:
                fields.append(("wp", [
                    ("addr", range(depth)),
                    ("en",   1),
                    ("data", complex(width)),
                ]))
            return Layout(fields)

        self.mem0 = Record(memory_port(size // 2, width, "rw"))
        self.mem1 = Record(memory_port(size // 2, width, "rw"))
        self.mem2 = Record(memory_port(size // 2, width, "rw"))
        self.trom = Record(memory_port(size // 2, width, "r"))

        self.size       = size
        self.width      = width

    def elaborate(self, platform):
        m = Module()

        consume = Record([
            ("tap",   range(self.size // 2)),
            ("stage", range(log2_int(self.size // 2) + 1)),
        ])
        consume.tap  .reset_less = True
        consume.stage.reset_less = True

        produce = Record.like(consume)
        produce.tap  .reset_less = True
        produce.stage.reset_less = True

        consume_stage_pow2 = Signal(log2_int(self.size // 2) + 1)
        m.d.comb += consume_stage_pow2.bit_select(consume.stage, width=1).eq(1)

        m.d.comb += [
            self.mem0.rp.addr.eq(consume.tap),
            self.mem1.rp.addr.eq(((consume.tap << 1) ^ consume_stage_pow2) >> 1),
            self.mem2.rp.addr.eq(self.mem1.rp.addr),
        ]

        x_mem_sel = Signal(2)
        m.d.sync += [
            x_mem_sel[0].eq(consume.tap.bit_select(consume.stage - 1, width=1) & (consume.stage != 0)),
            x_mem_sel[1].eq(consume.stage[0]),
        ]

        with m.Switch(x_mem_sel):
            with m.Case(0b00):
                m.d.comb += [
                    self.o.x0.eq(self.mem0.rp.data),
                    self.o.x1.eq(self.mem2.rp.data),
                ]
            with m.Case(0b01):
                m.d.comb += [
                    self.o.x0.eq(self.mem2.rp.data),
                    self.o.x1.eq(self.mem0.rp.data),
                ]
            with m.Case(0b10):
                m.d.comb += [
                    self.o.x0.eq(self.mem0.rp.data),
                    self.o.x1.eq(self.mem1.rp.data),
                ]
            with m.Case(0b11):
                m.d.comb += [
                    self.o.x0.eq(self.mem1.rp.data),
                    self.o.x1.eq(self.mem0.rp.data),
                ]

        m.d.comb += self.o.stb.eq(consume != 0)

        m.d.comb += [
            self.mem0.wp.addr.eq(produce.tap),
            self.mem1.wp.addr.eq(produce.tap),
            self.mem2.wp.addr.eq(produce.tap),
        ]

        mem_y_sel = Signal()
        m.d.comb += mem_y_sel.eq(produce.tap.bit_select(produce.stage, width=1))

        with m.If(mem_y_sel):
            m.d.comb += [
                self.mem0.wp.data.eq(self.i.y1),
                self.mem1.wp.data.eq(self.i.y0),
                self.mem2.wp.data.eq(self.i.y0),
            ]
        with m.Else():
            m.d.comb += [
                self.mem0.wp.data.eq(self.i.y0),
                self.mem1.wp.data.eq(self.i.y1),
                self.mem2.wp.data.eq(self.i.y1),
            ]

        trom_addr_step = Signal(range(self.size))
        m.d.comb += Cat(reversed(trom_addr_step)).bit_select(consume.stage, width=1).eq(1)

        trom_addr_next = Signal.like(self.trom.rp.addr)
        m.d.comb += trom_addr_next.eq(self.trom.rp.addr + trom_addr_step)

        m.d.comb += self.o.tw.eq(self.trom.rp.data)

        with m.FSM():
            with m.State("IDLE"):
                with m.If(self.start):
                    m.d.sync += [
                        consume.eq(0),
                        produce.eq(0),
                        self.trom.rp.addr.eq(0),
                    ]
                    m.next = "BUSY"

            with m.State("BUSY"):
                m.d.sync += [
                    consume.eq(consume + 1),
                    self.trom.rp.addr.eq(trom_addr_next),
                ]
                with m.If(self.i.stb):
                    m.d.sync += produce.eq(produce + 1)
                    m.d.comb += [
                        self.mem0.wp.en.eq(1),
                        self.mem1.wp.en.eq(~produce.stage[0]),
                        self.mem2.wp.en.eq( produce.stage[0]),
                    ]
                with m.If(produce.tap.all() & (produce.stage == log2_int(self.size // 2))):
                    m.d.comb += self.done.eq(1)
                    m.next = "IDLE"

        return m


class FFT(Elaboratable):
    def __init__(self, *, size, i_width, o_width, m_width, i_reversed=False):
        if not isinstance(size, int) or size <= 0 or size & size - 1:
            raise ValueError("Size must be a positive power-of-two integer, not {!r}"
                             .format(size))
        # assert m_width >= max(i_width, o_width) TODO

        self.size       = size
        self.i_width    = i_width
        self.o_width    = o_width
        self.m_width    = m_width
        self.i_reversed = i_reversed

        self.i = Record([
            ("addr", range(size)),
            ("en",   1),
            ("data", complex(i_width)),
        ])
        self.o = Record([
            ("addr", range(size)),
            ("data", complex(o_width)),
        ])

        self.start = Signal()
        self.ready = Signal()
        # self.scale = Signal(range(size)) TODO

    def elaborate(self, platform):
        m = Module()

        m.submodules.trom  = trom  = TwiddleROM(size=self.size, width=self.m_width)
        m.submodules.bf    = bf    = Butterfly(width=self.m_width, bias_width=self.m_width - 2, scale_bit=True)
        m.submodules.sched = sched = Scheduler(size=self.size, width=self.m_width)

        mem0 = Memory(width=2 * self.m_width, depth=self.size // 2)
        m.submodules.mem0_wp = mem0_wp = mem0.write_port()
        m.submodules.mem0_rp = mem0_rp = mem0.read_port()

        mem1 = Memory(width=2 * self.m_width, depth=self.size // 2)
        m.submodules.mem1_wp = mem1_wp = mem1.write_port()
        m.submodules.mem1_rp = mem1_rp = mem1.read_port()

        mem2 = Memory(width=2 * self.m_width, depth=self.size // 2)
        m.submodules.mem2_wp = mem2_wp = mem2.write_port()
        m.submodules.mem2_rp = mem2_rp = mem2.read_port()

        m.d.comb += [
            bf.i.stb.eq(sched.o.stb),
            bf.i.x0 .eq(sched.o.x0),
            bf.i.x1 .eq(sched.o.x1),
            bf.i.tw .eq(sched.o.tw),

            sched.i.stb.eq(bf.o.stb),
            sched.i.y0 .eq(bf.o.y0),
            sched.i.y1 .eq(bf.o.y1),

            sched.mem0.rp.data.eq(mem0_rp.data),
            sched.mem1.rp.data.eq(mem1_rp.data),
            sched.mem2.rp.data.eq(mem2_rp.data),

            trom.rp_addr.eq(sched.trom.rp.addr),
            sched.trom.rp.data.eq(trom.rp_data),
        ]

        i_addr_rev = Signal.like(self.i.addr)
        if self.i_reversed:
            # self.i.addr has already been bitreversed by user logic.
            m.d.comb += i_addr_rev.eq(self.i.addr)
        else:
            m.d.comb += i_addr_rev.eq(Cat(reversed(self.i.addr)))

        i_data_sext = Record(complex(self.m_width))
        m.d.comb += [
            i_data_sext.real.eq(self.i.data.real),
            i_data_sext.imag.eq(self.i.data.imag),
        ]

        o_data_sel = Signal()
        m.d.sync += o_data_sel.eq(~self.o.addr[-1])

        with m.If(o_data_sel):
            m.d.comb += self.o.data.eq(mem0_rp.data)
        with m.Else():
            if log2_int(self.size) % 2:
                m.d.comb += self.o.data.eq(mem1_rp.data)
            else:
                m.d.comb += self.o.data.eq(mem2_rp.data)

        with m.FSM():
            with m.State("INIT"):
                m.d.comb += [
                    mem0_wp.addr.eq(i_addr_rev[1:]),
                    mem1_wp.addr.eq(i_addr_rev[1:]),
                    mem2_wp.addr.eq(i_addr_rev[1:]),

                    mem0_wp.data.eq(i_data_sext),
                    mem1_wp.data.eq(i_data_sext),
                    mem2_wp.data.eq(i_data_sext),

                    mem0_wp.en.eq(self.i.en & ~i_addr_rev[0]),
                    mem1_wp.en.eq(self.i.en &  i_addr_rev[0]),
                    mem2_wp.en.eq(self.i.en &  i_addr_rev[0]),

                    mem0_rp.addr.eq(self.o.addr[:-1]),
                    mem1_rp.addr.eq(self.o.addr[:-1]),
                    mem2_rp.addr.eq(self.o.addr[:-1]),

                    self.ready.eq(1),
                ]
                with m.If(self.start):
                    m.d.comb += sched.start.eq(1)
                    m.next = "BUSY"

            with m.State("BUSY"):
                m.d.comb += [
                    mem0_wp.addr.eq(sched.mem0.wp.addr),
                    mem1_wp.addr.eq(sched.mem1.wp.addr),
                    mem2_wp.addr.eq(sched.mem2.wp.addr),

                    mem0_wp.data.eq(sched.mem0.wp.data),
                    mem1_wp.data.eq(sched.mem1.wp.data),
                    mem2_wp.data.eq(sched.mem2.wp.data),

                    mem0_wp.en.eq(sched.mem0.wp.en),
                    mem1_wp.en.eq(sched.mem1.wp.en),
                    mem2_wp.en.eq(sched.mem2.wp.en),

                    mem0_rp.addr.eq(sched.mem0.rp.addr),
                    mem1_rp.addr.eq(sched.mem1.rp.addr),
                    mem2_rp.addr.eq(sched.mem2.rp.addr),
                ]
                with m.If(sched.done):
                    m.d.comb += bf.reset.eq(1)
                    m.next = "INIT"

        return m


from nmigen.sim import *

if __name__ == "__main__":
    data = [0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc001, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6, 0x3fff, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861, 0x6d41, 0xb32a, 0xcccc, 0x0e9e, 0xfa16, 0x70a6, 0xc9de, 0xb9ce, 0x14c3, 0xefbb, 0x6da8, 0xe408, 0xa8bd, 0x178a, 0xe9d5, 0x64dc, 0x0000, 0x9b24, 0x162b, 0xe876, 0x5743, 0x1bf8, 0x9258, 0x1045, 0xeb3d, 0x4632, 0x3622, 0x8f5a, 0x05ea, 0xf162, 0x3334, 0x4cd6, 0x92bf, 0xf79f, 0xf9ca, 0x1fe9, 0x5eaf, 0x9ca2, 0xe650, 0x0321, 0x0ddf, 0x6aab, 0xac9e, 0xd346, 0x0c01, 0xfe74, 0x703e, 0xc1d7, 0xc000, 0x130a, 0xf2b4, 0x6f56, 0xdb06, 0xae1e, 0x170b, 0xeb4a, 0x6862, 0xf697, 0x9f34, 0x171e, 0xe86e, 0x5c40, 0x12c2, 0x94ad, 0x12be, 0xe9e5, 0x4c2d, 0x2db8, 0x8fa9, 0x09d6, 0xef06, 0x39a6, 0x45bf, 0x90e4, 0xfcc6, 0xf6d1, 0x2647, 0x5958, 0x98a1, 0xec58, 0x0000, 0x13a8, 0x675f, 0xa6a8, 0xd9b9, 0x092f, 0x033a, 0x6f1c, 0xba41, 0xc65a, 0x10fa, 0xf62a, 0x7057, 0xd248, 0xb3d3, 0x161b, 0xed42, 0x6b53, 0xed3e, 0xa3c0, 0x1792, 0xe8e2, 0x60cc, 0x0969, 0x979e, 0x14b6, 0xe8f5, 0x51e2, 0x24fa, 0x90aa, 0x0d4c, 0xecf6]

    # from scipy.fft import fft
    # x = np.array([np.int16(n) for n in data])
    # y = fft(x)
    # for i, z in enumerate(y):
    #     print(i, int(z.real // 512), int(z.imag // 512))

    dut = FFT(size=512, i_width=16, o_width=16, m_width=16)
    sim = Simulator(dut)

    def process():
        for i, n in enumerate(data):
            yield dut.i.addr.eq(i)
            yield dut.i.data.real.eq(n)
            yield dut.i.en.eq(1)
            yield

        yield dut.i.en.eq(0)
        yield dut.start.eq(1)
        yield
        yield dut.start.eq(0)
        yield

        while not (yield dut.ready):
            yield
        yield

        for i in range(dut.size // 2):
            yield dut.o.addr.eq(i)
            yield; yield Delay()
            print("{} {} {}".format(
                i,
                (yield dut.o.data.real),
                (yield dut.o.data.imag),
            ))

    sim.add_clock(1e-6)
    sim.add_sync_process(process)
    with sim.write_vcd("dump.vcd"):
        sim.run()
