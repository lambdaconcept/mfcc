from nmigen import *
from nmigen_boards.resources import *

from ..core.mfcc import MFCC
from ..misc import stream
from ..misc.magic import MagicInserter
from ..misc.led import SevenSegController

from ..io.i2s_mic import AudioReceiver
from nmigen_stdio.serial import AsyncSerial


class Top(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()
        m.submodules.mfcc = mfcc = MFCC(nfft=512, nfilters=32, nceptrums=16)
        m.submodules.magic = magic = MagicInserter()

        i2s_pins = platform.request("i2s_in", 0)
        m.submodules.mic  = mic  = AudioReceiver(clk_freq=100e6, sample_freq=16e3, i2s_pins=i2s_pins)

        m.submodules.mic_fifo = mic_fifo = stream.SyncFIFO([("data", 16)], 512, buffered=True)
        m.d.comb += [
            mic.source.connect(mic_fifo.sink),
            mic_fifo.source.connect(mfcc.sink),
            mfcc.source.connect(magic.sink),
        ]

        num = Signal(range(10))
        m.submodules.seven_ctrl = seven_ctrl = SevenSegController()
        seven_pins = platform.request("seven_seg", 0)
        m.d.comb += [
            seven_ctrl.val.eq(num),

            seven_pins.val.eq(seven_ctrl.leds),
            seven_pins.sel.o.eq(1),
        ]

        uart_pins = platform.request("uart", 1)
        m.submodules.serial = serial = AsyncSerial(divisor=int(100e6 / 1000000), pins=uart_pins)
        # m.d.comb += [
            # serial.tx.ack.eq(serial.rx.rdy),
            # serial.tx.data.eq(serial.rx.data),
            # serial.rx.ack.eq(serial.tx.rdy),

            # serial.tx.data.eq(ord('A')),
            # serial.tx.ack.eq(1),
        # ]

        tail = magic
        tail.source.ready.reset = 1

        tx_ack_nxt  = Signal()
        tx_data_nxt = Signal(8)
        with m.If(tail.source.valid & tail.source.ready):
            m.d.sync += [
                Cat(tx_data_nxt, serial.tx.data).eq(tail.source.data),
                tx_ack_nxt.eq(1),
                serial.tx.ack.eq(1),
                tail.source.ready.eq(0),
            ]

        with m.If(serial.tx.rdy & serial.tx.ack):
            with m.If(tx_ack_nxt):
                m.d.sync += [
                    serial.tx.data.eq(tx_data_nxt),
                    tx_ack_nxt.eq(0),
                ]
            with m.Else():
                m.d.sync += serial.tx.ack.eq(0)
                m.d.sync += tail.source.ready.eq(1)

        # # #

        m.d.comb += serial.rx.ack.eq(1)
        with m.If(serial.rx.rdy & serial.rx.ack):
            m.d.sync += num.eq(serial.rx.data)

        return m


from nmigen_boards.ecpix5 import *
# from nmigen_boards.arty_a7 import ArtyA7Platform
from nmigen.build import *

def build():
    platform = ECPIX585Platform()
    platform.add_resources([
        Resource("i2s_in", 0,
            Subsignal("da", Pins( "1", dir="i", conn=("pmod", 0))),
            Subsignal("ck", Pins( "2", dir="o", conn=("pmod", 0))),
            Subsignal("lr", Pins( "3", dir="o", conn=("pmod", 0))),
            Subsignal("ws", Pins( "4", dir="o", conn=("pmod", 0))),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        Resource("pmod", 1,
            Subsignal("d0", Pins( "1", dir="o", conn=("pmod", 1))),
            Subsignal("d1", Pins( "2", dir="o", conn=("pmod", 1))),
            Subsignal("d2", Pins( "3", dir="o", conn=("pmod", 1))),
            Subsignal("d3", Pins( "4", dir="o", conn=("pmod", 1))),
            Subsignal("d4", Pins( "7", dir="o", conn=("pmod", 1))),
            Subsignal("d5", Pins( "8", dir="o", conn=("pmod", 1))),
            Subsignal("d6", Pins( "9", dir="o", conn=("pmod", 1))),
            Subsignal("d7", Pins("10", dir="o", conn=("pmod", 1))),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        UARTResource(1,
            rx="1", tx="2", conn=("pmod", 4),
            attrs=Attrs(IO_TYPE="LVCMOS33", PULLMODE="UP")
        ),
        Resource("seven_seg", 0,
            Subsignal("val", PinsN("1 2 3 4 7 8 9", dir="o", conn=("pmod", 7))),
            Subsignal("sel", PinsN("10", dir="o", conn=("pmod", 7)))
        ),
    ])
    platform.build(Top(), name="top", build_dir="build", do_program=True)


if __name__ == "__main__":
    build()
