from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream
from mfcc.misc.mul import *


class Log2FixCalc(Elaboratable):
    def __init__(self, width, precision, multiplier_cls=Multiplier):
        self.i = Signal(width)
        self.o = Signal(width)
        self.start = Signal()
        self.done = Signal()
        
        self.width = width
        self.precision = precision
        #self.mul = Multiplier(self.width, self.width)
        self.mul = multiplier_cls(self.width, self.width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.mul = mul = self.mul 
        b = Signal(self.width)
        #y = Signal(self.width, signed=True)
        x = Signal(self.width)
        cnt = Signal(range(self.precision))
        z = Signal(self.width*2)

        m.d.comb += [
            mul.i_a.eq(z[:self.width]),
            mul.i_b.eq(z[:self.width])
        ]
        
        with m.FSM() as fsm:
            with m.State("START"):
                with m.If(self.start):
                    m.d.sync += [
                        b.eq(1 << (self.precision-1)),
                        self.o.eq(0),
                        x.eq(self.i),
                        #self.done.eq(0)
                    ]
                    m.next = "SHIFT-LEFT"
                with m.Else():
                    m.d.comb += self.done.eq(1)
                    
            with m.State("SHIFT-LEFT"):
                with m.If( x < (1 << self.precision)):
                    m.d.sync += [
                        x.eq(Cat(0, x)),
                        self.o.eq(self.o - (1 << self.precision))
                    ]
                with m.Else():
                    m.next = "SHIFT-RIGHT"

            with m.State("SHIFT-RIGHT"):
                with m.If( x >= (2 << self.precision)):
                    m.d.sync += [
                        x.eq(x[1:]),
                        self.o.eq(self.o + (1 << self.precision))
                    ]
                with m.Else():
                    m.d.sync += [
                        cnt.eq(self.precision-1),
                        z.eq(x),
                        mul.start.eq(1)
                    ]
                    m.next = "CALC"

            with m.State("CALC"):
                with m.If(cnt):
                    with m.If(mul.done):
                        m.d.sync += [
                            cnt.eq(cnt -1),
                            b.eq(b[1:]),
                            mul.start.eq(1)
                        ]
                        with m.If(mul.o[self.precision:] >= (2 << self.precision)):
                            m.d.sync += [
                                z.eq(mul.o[self.precision+1:]),
                                self.o.eq(self.o + b)
                            ]
                        with m.Else():
                            m.d.sync += z.eq(mul.o[self.precision:])
                    with m.Else():
                        m.d.sync += [
                            mul.start.eq(0)
                        ]
                with m.Else():
                    m.d.sync += [
                        mul.start.eq(0),
                        #self.done.eq(1),
                    ]
                    m.next="START"
            return m


class Log2Fix(Elaboratable):
    def __init__(self, width, precision, multiplier_cls=Multiplier):
        self.sink = stream.Endpoint([("data", width)])
        self.source = stream.Endpoint( [("data", width)] )
        self.log2 = Log2FixCalc(width=width, precision=precision, multiplier_cls=multiplier_cls)
        self.width = width
        
    def elaborate(self, platform):
        sink = self.sink
        source = self.source
        m = Module()
        m.submodules.log2 = self.log2
        busy = Signal()
        consumed = sink.valid & ~busy
        produced = source.valid & source.ready

        m.d.comb += [
            self.log2.i.eq(sink.data),
            source.data.eq(self.log2.o),
            self.log2.start.eq(consumed),
            sink.ready.eq(produced),
            source.valid.eq(sink.valid & self.log2.done),
            source.last.eq(self.sink.last),
        ]

        with m.If(consumed & ~produced):
            m.d.sync += busy.eq(1)
        with m.Elif(produced):
            m.d.sync += busy.eq(0)

        return m

    

                    
if __name__ == "__main__":
    precision = 16
    dut = Log2Fix(37, precision, multiplier_cls=Multiplier)

    def bench():
        yield dut.sink.data.eq(2207315)
        yield dut.sink.valid.eq(1)
        yield dut.source.ready.eq(0)
        yield
        i=0
        for i in range(500):
            i=i+1
            yield
            if((yield dut.sink.ready)):
                yield dut.sink.valid.eq(0)
                for t in range(40):
                    yield
                yield dut.sink.valid.eq(1)
                
            if((yield dut.source.valid)):
                print((yield dut.source.data)/(1 << precision))
                yield dut.source.ready.eq(1)
                yield dut.sink.data.eq(20 << 10)

        
    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("log2.vcd"):
        sim.run()
