from nmigen import *
from nmigen.sim import Simulator
from mfcc.misc import stream
from mfcc.misc.mul import *

class PowerSpectrumCalc(Elaboratable):
    def __init__(self, width=16,  multiplier_cls=Multiplier):
        self.i_r = Signal((width, True))
        self.i_i = Signal((width, True))
        self.o = Signal(2 * width)
        self.start = Signal()
        self.done = Signal()

        self.mul_r = multiplier_cls((width, True), (width, True))
        self.mul_i = multiplier_cls((width, True), (width, True))
        
    def elaborate(self, platform):
        m = Module()
        m.submodules.mul_i = mul_i = self.mul_i
        m.submodules.mul_r = mul_r = self.mul_r

        m.d.comb += [
            self.mul_r.i_a.eq(self.i_r),
            self.mul_r.i_b.eq(self.i_r),
            self.mul_i.i_a.eq(self.i_i),
            self.mul_i.i_b.eq(self.i_i),

            self.done.eq(self.mul_r.done & self.mul_i.done),
            self.mul_r.start.eq(self.start),
            self.mul_i.start.eq(self.start),

            self.o.eq(self.mul_i.o + self.mul_r.o),
        ]
        return m
    
        
class PowerSpectrum(Elaboratable):
    def __init__(self, width=16, width_output=24, multiplier_cls=Multiplier):
        self.sink = stream.Endpoint([("data_r", (width, True)), ("data_i", (width, True))])
        self.source = stream.Endpoint( [("data", width_output)] )
        self.pow2 = PowerSpectrumCalc(width=width, multiplier_cls=multiplier_cls)
        self.width_output = width_output
        self.width = width

    def elaborate(self, platform):
        sink = self.sink
        source = self.source
        last = Signal()
        m = Module()
        m.submodules.pow2 = pow2 = self.pow2
        busy = Signal()
        consumed = sink.valid & ~busy
        produced = source.valid & source.ready

        m.d.comb += [
            pow2.i_r.eq(sink.data_r),
            pow2.i_i.eq(sink.data_i),
            source.data.eq(pow2.o[-self.width_output:]),
            pow2.start.eq(consumed),
            sink.ready.eq(produced),
            source.valid.eq(sink.valid & pow2.done),
            source.last.eq(sink.last),
        ]

        with m.If(consumed & ~produced):
            m.d.sync += busy.eq(1)
        with m.Elif(produced):
            m.d.sync += busy.eq(0)

        return m

    
if __name__ == "__main__":
    dut = PowerSpectrum(width=16, multiplier_cls=Multiplier)
    def bench():
        yield dut.sink.data_r.eq(65535)
        yield dut.sink.data_i.eq(65535)
        yield dut.sink.valid.eq(1)
        yield dut.source.ready.eq(0)
        yield

        for j in range(10):
            for i in range(40):
                yield
            yield dut.source.ready.eq(1)
            yield
            yield dut.source.ready.eq(0)
            yield
            if j == 5:
                yield dut.sink.last.eq(1)
            else:
                yield dut.sink.last.eq(0)
            print((yield dut.source.data))



    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("power.vcd"):
        sim.run()
