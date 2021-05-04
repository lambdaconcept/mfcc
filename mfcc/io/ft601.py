from nmigen import *
from nmigen.hdl.xfrm import DomainRenamer

from nmigen_soc import wishbone

from ..misc import stream


__all__ = ["FT601PHY", "FT601WishboneBridge"]


class FT601PHY(Elaboratable):
    def __init__(self, pads, data_width=32, timeout=64):
        self.read_fifo  = stream.AsyncFIFO([("data", data_width)], depth=8, w_domain="ft601", r_domain="sync")
        self.write_fifo = stream.AsyncFIFO([("data", data_width)], depth=8, w_domain="sync",  r_domain="ft601")
        self.read_buffer = DomainRenamer("ft601")(stream.SyncFIFO([("data", data_width)], depth=16))

        self.sink   = self.write_fifo.sink
        self.source = self.read_fifo.source

        self.pads       = pads
        self.data_width = data_width
        self.timeout    = timeout

    def elaborate(self, platform):
        m = Module()

        read_fifo = m.submodules.read_fifo = self.read_fifo
        read_buffer = m.submodules.read_buffer = self.read_buffer
        write_fifo = m.submodules.write_fifo = self.write_fifo

        m.d.comb += read_buffer.source.connect(read_fifo.sink)

        data_w = Signal(self.data_width)
        _data_w = Signal(self.data_width)
        m.d.ft601 += _data_w.eq(data_w)

        for i in range(self.data_width):
            m.submodules += Instance("ODDR",
                p_DDR_CLK_EDGE="SAME_EDGE",
                i_C=ClockSignal("ft601"), i_CE=Const(1), i_S=Const(0), i_R=Const(0),
                i_D1=_data_w[i], i_D2=data_w[i], o_Q=self.pads.data.o[i]
            )

        rd_n = Signal()
        _rd_n = Signal(reset=1)
        wr_n = Signal()
        _wr_n = Signal(reset=1)
        oe_n = Signal()
        _oe_n = Signal(reset=1)
        m.d.ft601 += [
            _rd_n.eq(rd_n),
            _wr_n.eq(wr_n),
            _oe_n.eq(oe_n),
        ]
        m.submodules += [
            Instance("ODDR",
                     p_DDR_CLK_EDGE="SAME_EDGE",
                     i_C=ClockSignal("ft601"), i_CE=Const(1), i_S=Const(0), i_R=Const(0),
                     i_D1=_rd_n, i_D2=rd_n, o_Q=self.pads.rd_n
            ),
            Instance("ODDR",
                     p_DDR_CLK_EDGE="SAME_EDGE",
                     i_C=ClockSignal("ft601"), i_CE=Const(1), i_S=Const(0), i_R=Const(0),
                     i_D1=_wr_n, i_D2=wr_n, o_Q=self.pads.wr_n
            ),
            Instance("ODDR",
                     p_DDR_CLK_EDGE="SAME_EDGE",
                     i_C=ClockSignal("ft601"), i_CE=Const(1), i_S=Const(0), i_R=Const(0),
                     i_D1=_oe_n, i_D2=oe_n, o_Q=self.pads.oe_n
            )
        ]

        m.d.comb += [
            self.pads.be.eq(0xf),
            self.pads.siwua.eq(1),
            self.pads.data.oe.eq(oe_n)
        ]

        tempsendval = Signal(self.data_width)
        temptosend = Signal()

        tempreadval = Signal(self.data_width)
        temptoread = Signal()

        wants_read = Signal()
        wants_write = Signal()
        cnt_write = Signal(range(self.timeout+2))
        cnt_read = Signal(range(self.timeout+2))

        first_write = Signal()

        m.d.comb += [
            wants_read.eq(~temptoread & ~self.pads.rxf_n),
            wants_write.eq((temptosend | write_fifo.source.valid) & (self.pads.txe_n == 0))
        ]

        write_fifo_source_valid_r = Signal()
        m.d.ft601 += write_fifo_source_valid_r.eq(write_fifo.source.valid)

        with m.FSM(domain="ft601") as fsm:
            with m.State("IDLE"):
                m.d.comb += [
                    rd_n.eq(1),
                    wr_n.eq(1)
                ]
                with m.If(wants_write):
                    m.d.comb += oe_n.eq(1)
                    m.d.ft601 += [
                        cnt_write.eq(0),
                        first_write.eq(1)
                    ]
                    m.next = "WRITE"
                with m.Elif(wants_read):
                    m.d.comb += oe_n.eq(0)
                    m.next = "RDWAIT"
                with m.Else():
                    m.d.comb += oe_n.eq(1)

            with m.State("WRITE"):
                with m.If(wants_read):
                    m.d.ft601 += cnt_write.eq(cnt_write+1)
                m.d.ft601 += first_write.eq(0)
                m.d.comb += rd_n.eq(1)
                with m.If(self.pads.txe_n):
                    m.d.comb += [
                        oe_n.eq(1),
                        wr_n.eq(1),
                        write_fifo.source.ready.eq(0)
                    ]
                    with m.If(write_fifo_source_valid_r & ~first_write):
                        m.d.ft601 += temptosend.eq(1)
                    m.next = "IDLE"
                with m.Elif(temptosend):
                    m.d.comb += [
                        oe_n.eq(1),
                        data_w.eq(tempsendval),
                        wr_n.eq(0)
                    ]
                    m.d.ft601 += temptosend.eq(0)
                with m.Elif(cnt_write > self.timeout):
                    m.d.comb += oe_n.eq(0)
                    m.next = "RDWAIT"
                with m.Elif(write_fifo.source.valid):
                    m.d.comb += [
                        oe_n.eq(1),
                        data_w.eq(write_fifo.source.data),
                        write_fifo.source.ready.eq(1)
                    ]
                    m.d.ft601 += [
                        tempsendval.eq(write_fifo.source.data),
                        temptosend.eq(0)
                    ]
                    m.d.comb += wr_n.eq(0)
                with m.Else():
                    m.d.comb += [
                        oe_n.eq(1),
                        wr_n.eq(1)
                    ]
                    m.d.ft601 += temptosend.eq(0)
                    m.next = "IDLE"

            with m.State("RDWAIT"):
                m.d.comb += [
                    rd_n.eq(0),
                    oe_n.eq(0),
                    wr_n.eq(1)
                ]
                m.d.ft601 += cnt_read.eq(0)
                m.next = "READ"

            with m.State("READ"):
                with m.If(wants_write):
                    m.d.ft601 += cnt_read.eq(cnt_read+1)
                m.d.comb += wr_n.eq(1)
                with m.If(self.pads.rxf_n):
                    m.d.comb += [
                        oe_n.eq(0),
                        rd_n.eq(1)
                    ]
                    m.next = "IDLE"
                with m.Elif(cnt_read > self.timeout):
                    m.d.ft601 += [
                        cnt_write.eq(0),
                        first_write.eq(1)
                    ]
                    m.next = "WRITE"
                    m.d.comb += oe_n.eq(1)
                with m.Else():
                    m.d.comb += [
                        oe_n.eq(0),
                        read_buffer.sink.valid.eq(1),
                        read_buffer.sink.data.eq(self.pads.data.i)
                    ]
                    m.d.ft601 += tempreadval.eq(self.pads.data.i)
                    with m.If(read_buffer.sink.ready):
                        m.d.comb += rd_n.eq(0)
                    with m.Else():
                        m.d.ft601 += temptoread.eq(1)
                        m.next = "IDLE"
                        m.d.comb += rd_n.eq(1)

        with m.If(~fsm.ongoing("READ") & temptoread):
            with m.If(read_buffer.sink.ready):
                m.d.ft601 += temptoread.eq(0)
            m.d.comb += [
                read_buffer.sink.data.eq(tempreadval),
                read_buffer.sink.valid.eq(1),
            ]

        return m


class FT601WishboneBridge(Elaboratable):
    def __init__(self):
        self.sink   = stream.Endpoint([("data", 32)])
        self.source = stream.Endpoint([("data", 32)])

        self.bus = wishbone.Interface(addr_width=32, data_width=32, features={"cti", "bte"})

    def elaborate(self, platform):
        m = Module()

        command = Record([
            ("write",      1),
            ("reserved0",  3),
            ("const",      1),
            ("reserved1",  3),
            ("count",     24),
            ("addr",      32),
        ])

        cur = Record.like(self.bus)
        nxt = Record.like(self.bus)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.comb += self.sink.ready.eq(1)
                with m.If(self.sink.valid):
                    last = Signal()
                    m.d.sync += command.eq(Cat(command[32:], self.sink.data)),
                    m.d.sync += last.eq(~last)
                    with m.If(last):
                        m.next = "DECODE"

            with m.State("DECODE"):
                # Read/writes of empty amounts are ignored.
                with m.If(command.count != 0):
                    m.d.sync += nxt.adr.eq(command.addr),
                    with m.If(command.count == 1):
                        m.d.sync += nxt.cti.eq(wishbone.CycleType.END_OF_BURST)
                    with m.Elif(command.const):
                        m.d.sync += nxt.cti.eq(wishbone.CycleType.CONST_BURST)
                    with m.Else():
                        m.d.sync += nxt.cti.eq(wishbone.CycleType.INCR_BURST)
                    with m.If(command.write):
                        m.next = "WRITE"
                    with m.Else():
                        m.next = "READ"

            with m.State("WRITE"):
                m.d.comb += [
                    self.bus.cyc.eq(1),
                    self.bus.we.eq(1),
                    self.bus.sel.eq(1),
                    self.bus.bte.eq(wishbone.BurstTypeExt.LINEAR),
                ]
                with m.If(self.bus.ack):
                    with m.If(cur.cti == wishbone.CycleType.END_OF_BURST):
                        m.next = "IDLE"
                    m.d.comb += [
                        self.bus.stb.eq(nxt.stb),
                        self.bus.adr.eq(nxt.adr),
                        self.bus.dat_w.eq(nxt.dat_w),
                        self.bus.cti.eq(nxt.cti),
                    ]
                    m.d.sync += cur.stb.eq(0)
                with m.Else():
                    m.d.comb += [
                        self.bus.stb.eq(cur.stb),
                        self.bus.adr.eq(cur.adr),
                        self.bus.dat_w.eq(cur.dat_w),
                        self.bus.cti.eq(cur.cti),
                    ]
                with m.If(~cur.stb | self.bus.ack):
                    m.d.sync += [
                        cur.stb.eq(nxt.stb),
                        cur.adr.eq(nxt.adr),
                        cur.dat_w.eq(nxt.dat_w),
                        cur.cti.eq(nxt.cti),
                    ]
                    with m.If(nxt.stb):
                        m.d.sync += nxt.stb.eq(0)
                        with m.If(~command.const):
                            m.d.sync += nxt.adr.eq(nxt.adr + 1)
                with m.If((~nxt.stb | self.bus.ack) & (command.count != 0)):
                    m.d.comb += self.sink.ready.eq(1)
                    with m.If(self.sink.valid):
                        m.d.sync += [
                            nxt.stb.eq(1),
                            nxt.dat_w.eq(self.sink.data),
                        ]
                        m.d.sync += command.count.eq(command.count - 1)
                        with m.If(command.count == 1):
                            m.d.sync += nxt.cti.eq(wishbone.CycleType.END_OF_BURST)

            with m.State("READ"):
                m.d.comb += [
                    self.bus.cyc.eq(1),
                    self.bus.stb.eq(self.source.ready),
                    self.bus.adr.eq(nxt.adr),
                    self.bus.sel.eq(1),
                    self.bus.cti.eq(nxt.cti),
                    self.bus.bte.eq(wishbone.BurstTypeExt.LINEAR),
                ]
                with m.If(command.count == 2):
                    m.d.sync += nxt.cti.eq(wishbone.CycleType.END_OF_BURST)
                m.d.comb += [
                    self.source.valid.eq(self.bus.ack),
                    self.source.data.eq(self.bus.dat_r),
                    self.source.last.eq(command.count == 1),
                ]
                with m.If(self.source.ready & self.source.valid):
                    with m.If(~command.const):
                        m.d.sync += nxt.adr.eq(nxt.adr + 1)
                    m.d.sync += command.count.eq(command.count - 1)
                    with m.If(command.count == 1):
                        m.next = "IDLE"

        return m
