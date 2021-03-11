from nmigen import *
from nmigen.sim import Simulator
import numpy as np
from mfcc.misc import stream
from mfcc.misc.mul import *
import math


def freq_to_mel(freq):
    return 2595.0 * np.log10(1.0 + freq / 700.0)

def met_to_freq(mels):
    return 700.0 * (10.0**(mels / 2595.0) - 1.0)

def get_filter_points(fmin, fmax, mel_filter_num, FFT_size, sample_rate=44100):
    fmin_mel = freq_to_mel(fmin)
    fmax_mel = freq_to_mel(fmax)
    mels = np.linspace(fmin_mel, fmax_mel, num=mel_filter_num+2)
    freqs = met_to_freq(mels)
    return np.floor((FFT_size + 1) / sample_rate * freqs).astype(int)

def calc_filters(tab, wsize=9):
    output = []
    max_acc = 1 << ((2*wsize))
    print(tab)
    for i in range(len(tab)-1):
        diff = tab[i+1] - tab[i] -1
        if(diff):
            step = (max_acc//diff) -1
        else:
            step = max_acc-1
        output.append(step)

    return output


class FilterBank(Elaboratable):
    def __init__(
            self,
            width=24,
            width_output=24,
            width_mul=None,
            sample_rate=16000,
            nfft=512,
            ntap=16,
            multiplier_cls=Multiplier
    ):        
        if width_mul == None:
            self.width_mul = width
        else:
            self.width_mul = width_mul

        self.width = width
        self.nfft = nfft
        self.ntap = ntap
        self.width_output = width_output
        self.mul = multiplier_cls(width, self.width_mul)
        self.sink = stream.Endpoint([("data", width)])
        self.source = stream.Endpoint([("data", width_output)])
        self.points = get_filter_points(0, sample_rate/2, ntap, nfft, sample_rate=sample_rate)
        self.filters = calc_filters(self.points, wsize=self.width_mul)
        
    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()
        mem = Memory(depth=len(self.filters), width=2*self.width_mul, init=self.filters)
        m.submodules.mem_rp = mem_rp = mem.read_port(domain="comb")
        m.submodules.mul = mul = self.mul
        filter_adr = Signal(range(len(self.filters)))

        acc = Signal(2*self.width_mul)
        
        maxvalrange = int(math.log2(self.points[-1] - self.points[-3])) + self.width + self.width_mul


        rega = Signal(maxvalrange)
        regb = Signal(maxvalrange)
        mult = Signal(self.width + self.width_mul)

        
        m.d.comb += [
            mem_rp.addr.eq(filter_adr),
            mul.i_a.eq(sink.data),
            mul.i_b.eq(acc[self.width_mul:]),
            mult.eq(mul.o)
        ]

        busy = Signal()
        sending = source.valid
        consumed = sink.valid & ~busy & ~sending
        produced = mul.done & sink.valid & ~sending
        highest = acc[self.width_mul:] == ((1 << self.width_mul)-1)
        last = sink.last # filter_adr == self.ntap

        m.d.comb += [
            mul.start.eq(consumed),
            sink.ready.eq(produced),
            #source.valid.eq(sink.valid & pow2.done),
        ]
        with m.If(consumed & ~produced):
            m.d.sync += busy.eq(1)
        with m.Elif(produced):
            m.d.sync += busy.eq(0)

        with m.If(produced):
            #we reached the highest                                           
            with m.If(highest):

                with m.If(last):
                    m.d.sync += filter_adr.eq(0),
                with m.Else():
                    m.d.sync += filter_adr.eq(filter_adr+1),

                m.d.sync += [
                    acc.eq(0),
                    #regb.eq(rega + sink.data ),
                    regb.eq(rega + (sink.data << self.width_mul)),
                    rega.eq(0),
                ]

            #we are growing                                                   
            with m.Else():
                m.d.sync += [
                    #rega.eq(rega + mult[-self.width:]),
                    #regb.eq(regb + sink.data - mult[-self.width:]),

                    rega.eq(rega + mult),
                    regb.eq(regb + (sink.data << self.width_mul) - mult),
                    
                    acc.eq(acc + mem_rp.data),
                ]
            
        # stream output path
        with m.If(produced & highest & (filter_adr != 0)):
            with m.If(regb[-self.width_output:] == 0):
                #we output 1 instead of 0 in this case in order to allow log(1) later
                #as log(0) is an error
                m.d.sync += source.data.eq(1)
            with m.Else():
                m.d.sync += source.data.eq(regb[-self.width_output:])
                
            m.d.sync += [
                source.last.eq(last),
                sending.eq(1),
            ]
        with m.Elif(sending & source.ready):
            m.d.sync += [
                source.last.eq(0),
                sending.eq(0),
            ]
        
        return m

        
    
if __name__ == "__main__":
    dut = FilterBank(width=31, width_output=32, multiplier_cls=MultiplierShifter)
    def bench():
        #yield dut.sink.data.eq(2**24-1)
        yield dut.sink.data.eq(1234)
        yield dut.sink.valid.eq(1)
        yield
        for i in range(100):
            yield
        for i in range(10000):
            if i == 600:
                yield dut.sink.last.eq(1)

            if (yield dut.source.valid) and (yield dut.source.ready):
                print((yield dut.source.data))
            yield dut.source.ready.eq(dut.source.valid)
            yield


    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("filterbank.vcd"):
        sim.run()
