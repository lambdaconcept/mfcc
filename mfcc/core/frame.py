from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream
from mfcc.misc.mem import *

class RotatingCounter(Elaboratable):
    def __init__(self, size):
        self.size = size

        self.val = Signal(range(size))      # current counter value
        self.nxt = Signal(range(size))      # next expected value

        # commands
        self.inc = Signal()                 # increment the counter value (+1)
        self.set = Signal()                 # set the counter to opval
        self.add = Signal()                 # increment the counter by opval (+opval)
        self.opval = Signal(range(size))    # operand value

    def elaborate(self, platform):
        val = self.val
        opval = self.opval
        nxt = self.nxt

        m = Module()

        # command set
        with m.If(self.set):
            m.d.comb += nxt.eq(opval)

        # command add
        with m.Elif(self.add):
            with m.If(val + opval >= self.size):
                m.d.comb += nxt.eq(val + opval - self.size)
            with m.Else():
                m.d.comb += nxt.eq(val + opval)

        # command increment or no command
        with m.Else():
            with m.If(val == self.size - 1):
                m.d.comb += nxt.eq(0)
            with m.Else():
                m.d.comb += nxt.eq(val + 1)

        with m.If(self.set | self.add | self.inc):
            m.d.sync += val.eq(nxt)

        return m

class Frame(Elaboratable):
    def __init__(self, width=16, windowlen=400, stepsize=160, nfft=512):
        assert(windowlen <= nfft)
        self.width = width
        self.windowlen = windowlen
        self.stepsize = stepsize
        self.nfft = nfft

        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()
        mem = Memory1W1R(depth=self.windowlen, width=self.width)
        m.submodules.mem = mem

        lvl = Signal(range(self.windowlen + 1))                         # level represents the amount of valid data in the memory bank
        firstfill = Signal(reset=1)
        m.submodules.addr_i = addr_i = RotatingCounter(self.windowlen)
        m.submodules.addr_o = addr_o = RotatingCounter(self.windowlen)
        m.submodules.step_o = step_o = RotatingCounter(self.windowlen)  # store the addr of the beginning of the next frame
        m.submodules.count_o = count_o = RotatingCounter(self.nfft)     # how many was output in the current frame

        empty = (lvl == 0)
        full = (lvl == self.windowlen)
        padding = (count_o.val >= self.windowlen)
        datasent = (source.valid & source.ready)
        jumping = (datasent & source.last)
        stepfull = (addr_i.nxt == step_o.val)

        # memory level monitor
        #  when jumping back to a new frame we consider that
        #  the amount of data buffered in the memory bank has been increased
        #  by the size of the jump (windowlen - stepsize)
        with m.If(jumping):
            m.d.sync += lvl.eq(lvl + addr_i.inc - addr_o.inc
                                   + self.windowlen - self.stepsize)
        with m.Else():
            m.d.sync += lvl.eq(lvl + addr_i.inc  - addr_o.inc)

        # step overrun detector
        blocked = Signal()
        with m.If(jumping):
            m.d.sync += blocked.eq(0)
        with m.Elif(addr_i.inc & stepfull):
            with m.If(firstfill): # dont block on the very first fill
                m.d.sync += firstfill.eq(0)
            with m.Else():
                m.d.sync += blocked.eq(1)

        # beginning of a new frame: store the next frame addr
        with m.If(datasent & source.first):
            m.d.comb += [
                step_o.opval.eq(self.stepsize),
                step_o.add.eq(1),
            ]

        # end of the current frame: jump to the next frame addr
        with m.If(datasent & source.last):
            m.d.comb += [
                addr_o.opval.eq(step_o.val),
                addr_o.set.eq(1),
            ]

        # memory
        m.d.comb += [
            mem.wp.addr.eq(addr_i.val),
            mem.wp.data.eq(sink.data),
            source.data.eq(Mux(padding, 0, mem.rp.data)),
        ]

        # output stream delimiters
        m.d.comb += [
            source.first.eq(count_o.val == 0),
            source.last.eq(count_o.nxt == 0),
        ]

        # the memory is not full: accept data from sink
        with m.If(~full & ~blocked):
            with m.If(sink.valid):
                m.d.comb += [
                    sink.ready.eq(1),
                    mem.wp.en.eq(1),
                    addr_i.inc.eq(1),
                ]

        # we have data to send on source
        with m.If(~empty | padding):
            m.d.comb += [
                source.valid.eq(1),
                mem.rp.addr.eq(Mux(source.ready, addr_o.nxt, addr_o.val)),
            ]

            with m.If(source.ready):
                m.d.comb += count_o.inc.eq(1)
                with m.If(~padding):
                    m.d.comb += addr_o.inc.eq(1)

        # we cannot send data yet but load memory addr
        #  so the data is ready on next clk cycle
        with m.Else():
            m.d.comb += mem.rp.addr.eq(addr_o.val)

        return m

if __name__ == "__main__":
    dut = Frame(windowlen=25, stepsize=8, nfft=32)

    def bench_source_ready():
        yield dut.source.ready.eq(1)

        for i in range(256):
            yield dut.sink.data.eq(i)
            yield dut.sink.valid.eq(1)
            yield
            while not (yield dut.sink.ready):
                yield

    def bench_source_not_ready():
        j = 0
        yield dut.source.ready.eq(0)

        for i in range(256):
            yield dut.sink.data.eq(i)
            yield dut.sink.valid.eq(1)
            yield
            while not (yield dut.sink.ready):
                yield
                j += 1
                if j == 123:
                    yield dut.source.ready.eq(1)

    def bench_source_faster_than_sink():
        j = 0
        yield dut.source.ready.eq(1)

        for i in range(512):
            yield dut.sink.data.eq(j)
            yield dut.sink.valid.eq((i%11) == 0)
            yield
            if ((yield dut.sink.valid) and (yield dut.sink.ready)):
                j += 1
            if (yield dut.source.ready) and (yield dut.source.valid):
                print((yield dut.source.data))
                if (yield dut.source.last):
                    print()

    def bench_source_slower_than_sink():
        j = 0
        yield dut.source.ready.eq(0)

        for i in range(2048):
            yield dut.sink.data.eq(j)
            yield dut.sink.valid.eq((i%7) == 0)
            yield
            if ((yield dut.sink.valid) and (yield dut.sink.ready)):
                j += 1
            yield dut.source.ready.eq((i%13) == 0)
            if (yield dut.source.ready) and (yield dut.source.valid):
                print((yield dut.source.data))
                if (yield dut.source.last):
                    print()

    dut2 = Frame(windowlen=32, stepsize=8, nfft=32)

    def bench_nopadding():
        j = 0
        yield dut2.source.ready.eq(0)

        for i in range(2048):
            yield dut2.sink.data.eq(j)
            yield dut2.sink.valid.eq((i%7) == 0)
            yield
            if ((yield dut2.sink.valid) and (yield dut2.sink.ready)):
                j += 1
            yield dut2.source.ready.eq((i%13) == 0)
            if (yield dut2.source.ready) and (yield dut2.source.valid):
                print((yield dut2.source.data))
                if (yield dut2.source.last):
                    print()

    dut3 = Frame(windowlen=400, stepsize=160, nfft=512)

    def bench_big():
        j = 0
        yield dut3.source.ready.eq(0)

        for i in range(10000):
            yield dut3.sink.data.eq(j)
            yield dut3.sink.valid.eq((i%5) == 0)
            yield
            if ((yield dut3.sink.valid) and (yield dut3.sink.ready)):
                j += 1
            yield dut3.source.ready.eq((i%3) == 0)
            if (yield dut3.source.ready) and (yield dut3.source.valid):
                print((yield dut3.source.data))
                if (yield dut3.source.last):
                    print()

    sim = Simulator(dut3)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench_big)
    with sim.write_vcd("frame.vcd"):
        sim.run()
