import re
import os
import subprocess

from importlib import resources

from nmigen import *

from nmigen.lib.cdc import ResetSynchronizer
from nmigen.hdl.ast import Signal, SignalDict
from nmigen.build import *
from nmigen.vendor.xilinx_7series import *
from nmigen_boards.resources import *


__all__ = ["SDMUlatorCRG", "SDMUlatorPlatform"]


class SDMUlatorCRG(Elaboratable):
    def __init__(self):
        self.sync_reset = Signal()

    def elaborate(self, platform):
        m = Module()

        clk100_i   = platform.request("clk100", 0).i
        pll_locked = Signal()
        pll_fb     = Signal()
        pll_125    = Signal()
        pll_200    = Signal()

        m.submodules += Instance("PLLE2_BASE",
            p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

            # VCO @ 1000 MHz
            p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=10.0,
            p_CLKFBOUT_MULT=10, p_DIVCLK_DIVIDE=1,
            i_CLKIN1=clk100_i,
            i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

            # 125 MHz
            p_CLKOUT1_DIVIDE=8, p_CLKOUT1_PHASE=0.0,
            o_CLKOUT1=pll_125,

            # 200 MHz
            p_CLKOUT2_DIVIDE=5, p_CLKOUT2_PHASE=0.0,
            o_CLKOUT2=pll_200,
        )

        eos = Signal()
        m.submodules += Instance("STARTUPE2",
            o_EOS=eos,
        )

        # sync @ 125 MHz

        m.domains += ClockDomain("sync")
        m.submodules += Instance("BUFGCE",
            i_I=pll_125, i_CE=eos,
            o_O=ClockSignal("sync"),
        )
        m.submodules += ResetSynchronizer(
            arst=~pll_locked | self.sync_reset, domain="sync",
        )

        # idelay_ref @ 200 MHz

        m.domains += ClockDomain("idelay_ref")
        m.submodules += Instance("BUFGCE",
            i_I=pll_200, i_CE=eos,
            o_O=ClockSignal("idelay_ref"),
        )
        m.submodules += ResetSynchronizer(
            arst=~pll_locked, domain="idelay_ref",
        )

        # ft601 @ 100 MHz

        m.domains += ClockDomain("ft601")
        ft601_clk_i = platform.request("ft601_clk").i
        ft601_rst_o = platform.request("ft601_rst").o

        m.submodules += Instance("BUFGCE",
            i_I=ft601_clk_i, i_CE=eos,
            o_O=ClockSignal("ft601"),
        )
        m.d.comb += ft601_rst_o.eq(ResetSignal("ft601"))

        return m


class SDMUlatorPlatform(Xilinx7SeriesPlatform):
    device      = "xc7a200t"
    package     = "fbg484"
    speed       = "2L"
    default_clk = "clk100"
    resources   = [
        Resource("clk100", 0, Pins("R4", dir="i"),
                 Clock(100e6), Attrs(IOSTANDARD="LVCMOS33")),

        *LEDResources(pins="W22 Y22", attrs=Attrs(IOSTANDARD="LVCMOS33")),

        *ButtonResources(pins="Y21 AA21", attrs=Attrs(IOSTANDARD="LVCMOS33")),

        *SPIFlashResources(0,
            cs_n="T19", clk="L12", copi="P22", cipo="R22", wp_n="P21", hold_n="R21",
            attrs=Attrs(IOSTANDARD="LVCMOS33")
        ),

        # TODO:
        # Resource("ddr3", 0,
        #     Subsignal("rst",    PinsN("K6", dir="o")),
        #     Subsignal("clk",    DiffPairs("U9", "V9", dir="o"), Attrs(IOSTANDARD="DIFF_SSTL135")),
        #     Subsignal("clk_en", Pins("N5", dir="o")),
        #     Subsignal("cs",     PinsN("U8", dir="o")),
        #     Subsignal("we",     PinsN("P5", dir="o")),
        #     Subsignal("ras",    PinsN("P3", dir="o")),
        #     Subsignal("cas",    PinsN("M4", dir="o")),
        #     Subsignal("a",      Pins("R2 M6 N4 T1 N6 R7 V6 U7 R8 V7 R6 U6 T6 T8", dir="o")),
        #     Subsignal("ba",     Pins("R1 P4 P2", dir="o")),
        #     Subsignal("dqs",    DiffPairs("N2 U2", "N1 V2", dir="io"),
        #                         Attrs(IOSTANDARD="DIFF_SSTL135")),
        #     Subsignal("dq",     Pins("K5 L3 K3 L6 M3 M1 L4 M2 V4 T5 U4 V5 V1 T3 U3 R3", dir="io"),
        #                         Attrs(IN_TERM="UNTUNED_SPLIT_40")),
        #     Subsignal("dm",     Pins("L1 U1", dir="o")),
        #     Subsignal("odt",    Pins("R5", dir="o")),
        #     Attrs(IOSTANDARD="SSTL135", SLEW="FAST"),
        # ),

        Resource("sd_card", 0,
            Subsignal("cmd",        Pins("H18", dir="io")),
            Subsignal("clk",        Pins("J19", dir="o")),
            Subsignal("dat0",       Pins("G16", dir="io")),
            Subsignal("dat1",       Pins("H17", dir="io")),
            Subsignal("dat2",       Pins("G13", dir="io")),
            Subsignal("dat3",       Pins("G15", dir="io")),
            Subsignal("sel",        Pins("H15", dir="o")),
            Subsignal("dir_dat123", Pins("G17", dir="o")),
            Subsignal("dir_dat0",   Pins("H14", dir="o")),
            Subsignal("dir_cmd",    Pins("H13", dir="o")),
            Subsignal("clk_fb",     Pins("L19", dir="o")),
            Attrs(IOSTANDARD="LVCMOS18"),
        ),

        Resource("sd_card_emu", 0,
            Subsignal("cmd",        Pins("N22", dir="io")),
            Subsignal("clk",        Pins("K18", dir="i"), Clock(208e6)),
            Subsignal("dat0",       Pins("L21", dir="io")),
            Subsignal("dat1",       Pins("M21", dir="io")),
            Subsignal("dat2",       Pins("K21", dir="io")),
            Subsignal("dat3",       Pins("K22", dir="io")),
            Subsignal("sel",        Pins("H22", dir="o")),
            Subsignal("dir_dat123", Pins("M22", dir="o")),
            Subsignal("vcc",        Pins("AB2", dir="i"), Attrs(IOSTANDARD="LVCMOS33")),
            Subsignal("dir_dat0",   Pins("J21", dir="o")),
            Subsignal("dir_cmd",    Pins("J22", dir="o")),
            Subsignal("dat3_pup",   Pins("AB8", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
            Attrs(IOSTANDARD="LVCMOS18"),
        ),

        Resource("ft601_clk", 0, Pins("D17", dir="i"), Clock(100e6), Attrs(IOSTANDARD="LVCMOS33")),
        Resource("ft601_rst", 0, PinsN("C18", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
        Resource("ft601", 0,
            Subsignal("data",  Pins("C13 A13 B13 A14 C14 A15 B15 E13 A16 B16 B17 A18 B18 A19 C19 A20 "
                                    "B20 A21 B21 D14 E14 C15 D15 F14 C17 D16 E16 E17 D19 E19 F18 F19",
                                    dir="io")),
            Subsignal("be",    Pins("B22 C20 C22 D21", dir="o")),
            Subsignal("rxf_n", Pins("E21", dir="i")),
            Subsignal("txe_n", Pins("D22", dir="i")),
            Subsignal("rd_n",  Pins("G21", dir="o")),
            Subsignal("wr_n",  Pins("F21", dir="o")),
            Subsignal("oe_n",  Pins("G22", dir="o")),
            Subsignal("siwua", Pins("E22", dir="o")),
            Attrs(IOSTANDARD="LVCMOS33", SLEW="FAST"),
        ),

        # TODO:
        #Resource("usbc_cfg", 0,
        #),
    ]

    connectors = [
        Connector("cn",  4, " W19  W21  V22  V20 - "),
        Connector("cn",  7, "AB20 AA20 AB21 AB22 - "),
        Connector("cn", 14, "AB18 AA19  - "),
    ]

    def __init__(self):
        super().__init__(toolchain="Vivado")
        self._relative_clocks = SignalDict()

    def add_relative_clock_constraint(self, clock, source, ratio, duty_cycle):
        if not isinstance(clock, Signal):
            raise TypeError("Object {!r} is not a Signal".format(clock))
        if not isinstance(source, Signal):
            raise TypeError("Object {!r} is not a Signal".format(source))
        if not isinstance(ratio, (int, float)) or ratio <= 0:
            raise TypeError("Ratio must be a positive number, not {!r}".format(ratio))
        if not isinstance(duty_cycle, (int, float)) or duty_cycle < 0:
            raise TypeError("Duty cycle must be a non-negative number, not {!r}".format(duty_cycle))

        if clock in self._clocks:
            raise ValueError("Cannot add clock constraint on {!r}, which is already constrained "
                             "to {} Hz"
                             .format(clock, self._clocks[clock]))
        elif clock in self._relative_clocks:
            other_source, other_ratio, other_duty_cycle = self._relative_clocks[clock]
            raise ValueError("Cannot add clock constraint on {!r}, which is already constrained "
                             "to {}"
                             .format(clock, self._relative_clocks[clock], other_source))
        else:
            self._relative_clocks[clock] = source, float(ratio), float(duty_cycle)
        clock.attrs["keep"] = "TRUE"

    def iter_relative_clock_constraints(self):
        pin_i_to_port = SignalDict()
        for res, pin, port, attrs in self._ports:
            if hasattr(pin, "i"):
                if isinstance(res.ios[0], Pins):
                    pin_i_to_port[pin.i] = port.io
                elif isinstance(res.ios[0], DiffPairs):
                    pin_i_to_port[pin.i] = port.p
                else:
                    assert False

        for clock_signal, (source_signal, ratio, duty_cycle) in self._relative_clocks.items():
            port_signal = pin_i_to_port.get(source_signal)
            yield clock_signal, port_signal, ratio, duty_cycle

    @property
    def file_templates(self):
        return {
            **super().file_templates,
            "{{name}}-openocd.cfg": r"""
            interface ftdi
            ftdi_vid_pid 0x0403 0x6011
            ftdi_channel 0
            ftdi_layout_init 0x0098 0x008b
            reset_config none

            source [find cpld/xilinx-xc7.cfg]
            source [find cpld/jtagspi.cfg]
            adapter_khz 10000
            """,
            # We directly prepend the following constraints to the XDC file (rather than override
            # add_constraints in toolchain_prepare()) in order to benefit from templating.
            "{{name}}.xdc": r"""
            {% for clock_signal, source_signal, ratio, duty_cycle in platform.iter_relative_clock_constraints() %}
            create_generated_clock \
                -name {{clock_signal.name|ascii_escape}} \
                -source [get_ports {{source_signal.name|tcl_escape}}] \
                {% if ratio < 1 %}
                -divide_by {{(1/ratio)|int}} \
                {% else %}
                -multiply_by {{ratio|int}} \
                -duty_cycle {{duty_cycle}} \
                {% endif %}
                [get_nets {{clock_signal|hierarchy("/")|tcl_escape}}]
            {% endfor %}
            """ + super().file_templates["{{name}}.xdc"],
        }

    def toolchain_prepare(self, fragment, name, **kwargs):
        overrides = {
            "add_constraints": r"""
                set_property INTERNAL_VREF 0.675 [get_iobanks 35]
                # FIXME: don't hardcode clock names
                set_clock_groups \
                   -group {sd_card_emu_0__clk__io, sd_clk_div2, sd_clk_div2_n} \
                   -group {pll_125} \
                   -group {ft601_clk_0__io} \
                   -asynchronous
                # FIXME: set_clock_groups should be sufficient ?
                set_false_path \
                    -from [get_clocks {sd_clk_div2}] \
                    -to   [get_clocks {pll_125}]
                set_false_path \
                    -from [get_clocks {pll_125}] \
                    -to   [get_clocks {sd_clk_div2}]
                set_false_path \
                    -from [get_clocks {ft601_clk_0__io}] \
                    -to   [get_clocks {pll_125}]
                set_false_path \
                    -from [get_clocks {pll_125}] \
                    -to   [get_clocks {ft601_clk_0__io}]
            """,
            "script_before_bitstream": r"""
                set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
                set_property BITSTREAM.CONFIG.CONFIGRATE 40 [current_design]
            """,
        }
        return super().toolchain_prepare(fragment, name, **overrides, **kwargs)

    def toolchain_program(self, products, name, build_dir, flash=True):
        openocd = os.environ.get("OPENOCD", "openocd")
        with products.extract("{}-openocd.cfg".format(name)) as config_filename:
            if flash:
                bscan_spi_filename = resources.files("sdmulator.board") / "bscan_spi_xc7a200t.bit"
                with products.extract("{}.bin".format(name)) as binary_filename:
                    subprocess.check_call([openocd,
                        "-f", config_filename,
                        "-c", "transport select jtag; "
                              "init; "
                              "jtagspi_init 0 {}; "
                              "jtagspi_program {} 0x0; "
                              "xc7_program xc7.tap; "
                              "exit".format(bscan_spi_filename, binary_filename)
                    ])
            else:
                with products.extract("{}.bit".format(name)) as bitstream_filename:
                    subprocess.check_call([openocd,
                        "-f", config_filename,
                        "-c", "transport select jtag; "
                              "init; "
                              "pld load 0 {}; "
                              "exit".format(bitstream_filename)
                    ])


if __name__ == "__main__":
    from nmigen_boards.test.blinky import *
    platform = SDMUlatorPlatform()
    platform.build(Blinky(), do_program=True, program_opts={"flash": False})
