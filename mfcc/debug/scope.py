import os
import argparse

from migen import *

from litex.build.tools import write_to_file
from litex.build.generic_platform import *
from litex.build.xilinx.platform import XilinxPlatform

from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration import export

from litescope import LiteScopeAnalyzer


_io = [
    ("clk", 0, Pins(1)),
    ("rst", 0, Pins(1)),
    ("serial", 0,
        Subsignal("tx", 0, Pins(1)),
        Subsignal("rx", 0, Pins(1)),
    ),
    ("prb", 0,
        Subsignal("mfcc_reset", 0, Pins(1)),

        Subsignal("mfcc_sink_valid", 0, Pins(1)),
        Subsignal("mfcc_sink_ready", 0, Pins(1)),
        Subsignal("mfcc_sink_data", 0, Pins(16)),

        Subsignal("mfcc_source_valid", 0, Pins(1)),
        Subsignal("mfcc_source_ready", 0, Pins(1)),
        Subsignal("mfcc_source_data", 0, Pins(16)),
    ),
]

class DummyPlatform(XilinxPlatform):
    def __init__(self):
        super().__init__("", _io)


class LiteScopeSoC(SoCCore):
    csr_map = {
        "analyzer": 16,
        "io":       17,
    }
    csr_map.update(SoCCore.csr_map)

    def __init__(self, platform, clk_freq=int(125e6)):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.comb += [
            self.cd_sys.clk.eq(platform.request("clk")),
            self.cd_sys.rst.eq(platform.request("rst")),
        ]
        super().__init__(
            platform=platform, clk_freq=clk_freq,
            cpu_type="None",
            with_uart=True, uart_name="uartbone", uart_baudrate=1000000,
        )
        self.submodules.analyzer = LiteScopeAnalyzer(
            groups=platform.request("prb"), depth=512, trigger_depth=512,
        )


def main():
    platform = DummyPlatform()
    soc = LiteScopeSoC(platform)

    v_output = platform.get_verilog(soc, name="litescope")
    v_output.write("litescope.v")

    write_to_file("csr.csv", export.get_csr_csv(soc.csr_regions, soc.constants, soc.mem_regions))
    soc.analyzer.export_csv(v_output.ns, "analyzer.csv")


if __name__ == "__main__":
    main()
