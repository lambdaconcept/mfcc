from nmigen import *
from nmigen.sim import *
from mfcc.misc import stream
from mfcc.misc.fft import FFT
import numpy as np
from scipy.fftpack import *
from scipy.fft import fft

class DCTStream(Elaboratable):
    def __init__(self, width=16, nfft=16):
        self.width = width
        self.nfft = nfft
        self.sink = stream.Endpoint([("data", (width, True))])
        self.source = stream.Endpoint([("data", (width, True))])
        

    def elaborate(self, platform):
        sink = self.sink
        source = self.source

        m = Module()
        m.submodules.fft = mfft = FFT(size=self.nfft*4,
                                      i_width=self.width,
                                      o_width=self.width,
                                      m_width=self.width)

        cnt_fill = Signal(range(self.nfft*8))
        cnt_empty = Signal(range(self.nfft))
        #fft_adr = Signal(range(self.nfft))

        trig = Signal()

        m.d.comb += trig.eq(cnt_fill[0] ^ cnt_fill[1])
        
        m.d.comb += [
            
            mfft.i.addr.eq(Mux(trig, ~cnt_fill[1:], cnt_fill[1:])),

            mfft.i.data.real.eq(Mux(cnt_fill[0], sink.data, 0)),
            mfft.i.data.imag.eq(0),
            mfft.o.addr.eq(cnt_empty),
            source.data.eq(mfft.o.data.real),
        ]

        with m.FSM() as fsm:
            with m.State("FILL"):
                m.d.comb += [
                    mfft.i.en.eq(sink.valid),
                    sink.ready.eq(cnt_fill[:2] == 3)
                ]
                m.d.sync += [
                    source.valid.eq(0),
                    source.last.eq(0)
                ]

                with m.If(sink.valid ):
                    m.d.sync += cnt_fill.eq(cnt_fill+1)
                    with m.If(sink.last & sink.ready):
                        m.d.comb += mfft.start.eq(1)
                        m.next="WORK"

            with m.State("WORK"):
                with m.If(mfft.ready):
                    m.d.sync += cnt_empty.eq(0)
                    m.next = "EMPTY"

            with m.State("EMPTY"):
                m.d.sync += source.valid.eq(1)
                with m.If(source.ready):
                    m.d.sync += cnt_empty.eq(cnt_empty +1)
                    with m.If(cnt_empty == self.nfft -1):
                        m.d.sync += [
                            cnt_fill.eq(0),
                            source.last.eq(1)
                        ]
                        m.next = "FILL"

        return m




if __name__ == "__main__":
    
    data = [0x4000, 0x3e29, 0x8fc2, 0x018c, 0xf3ff, 0x2cba, 0x5362, 0x9555, 0xf221, 0xfcdf, 0x19b0, 0x635e, 0xa151, 0xe017, 0x0636, 0x0861]
    N=len(data)
    dut = DCTStream(nfft=N)

    def bench():
        val = []
        yield dut.source.ready.eq(1)
        yield dut.sink.valid.eq(1)
        for i in range(4*N):
            yield dut.sink.data.eq(data[i//4])
            yield dut.sink.last.eq(((1+i) % (N*4)) == 0)
            yield; yield Delay()
        p = 0
        yield dut.sink.valid.eq(0)
        yield dut.sink.last.eq(0)
        for i in range(5000):
            yield; yield Delay()
            if((yield dut.source.valid)):
                val.append(np.int16((yield dut.source.data)))
                #print(p, (yield dut.source.data_r), (yield dut.source.data_i))
                p = p+1
        print("FFT DCT:")
        print(val)

        """
        print("FFT scipy:")
        newdata = np.int16(data2)
        #print(newdata)
        print("DONE")
        myfft = fft(newdata)
        v = np.array(myfft.real//N)
        print(v.astype(int))


        print("\n")
        res = np.array([val[k] * 2 * np.exp(-1j*np.pi*k/(2*16)) for k in range(16)])
        print(res.real)

        print("\n")
        """
        tst = [np.int16(data[i]) for i in range(16)]
        
        
        #print(dct(tst, norm="ortho"))
        
        print(dct(tst)//64)

        
    sim = Simulator(dut)
    sim.add_clock(1e-6) # 1 MHz
    sim.add_sync_process(bench)
    with sim.write_vcd("dct.vcd"):
        sim.run()
