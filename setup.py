from setuptools import setup, find_packages


setup(
    name="mfcc",
    version="0.0.1",
    author="Lambdaconcept",
    author_email="contact@lambdaconcept.com",
    description="An MFCC core",
    #long_description="""TODO""",
    python_requires="~=3.7",
    setup_requires=["wheel", "setuptools"],
    install_requires=["nmigen"],
    extras_require={
        "toolchain": [
            "nmigen-yosys",
            "yowasp-yosys",
        ],
    },
    dependency_links=[
        "git+https://github.com/nmigen/nmigen.git#egg=nmigen",
    ],
    packages=find_packages(),
    package_data={"sdmulator.board": ["bscan_spi_xc7a200t.bit"]},
    entry_points={
        "console_scripts": [
            "wav2mfcc = mfcc.targets.wav2mfcc:build",
            "mic2mfcc = mfcc.targets.mic2mfcc:build",
            "mfcc-sim = mfcc.core.mfcc:test",
        ],
    },
    project_urls={
        "Source Code": "https://github.com/lambdaconcept/mfcc",
        "Bug Tracker": "https://github.com/lambdaconcept/mfcc/issues",
    },
)
