# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT

from setuptools import find_packages, setup

extras_require = {
    # These are all the drivers' dependencies. Optional dependencies are
    # listed as mandatory for the feature.
    "accucheck_reports": [],
    "contourusb": ["construct", "hidapi"],
    "fsinsulinx": ["construct", "hidapi"],
    "fslibre": ["construct", "hidapi"],
    "fsoptium": ["pyserial"],
    "fsprecisionneo": ["construct", "hidapi"],
    "otultra2": ["pyserial"],
    "otultraeasy": ["construct", "pyserial"],
    "otverio2015": ["construct"],
    "otverioiq": ["construct", "pyserial"],
    "sdcodefree": ["construct", "pyserial"],
    "td4277": ["construct", "pyserial", "hidapi"],
    # These are not drivers, but rather tools and features.
    "reversing_tools": ["usbmon-tools"],
    "dev": [
        "absl-py",
        "construct>=2.9",
        "mypy",
        "pre-commit",
        "pytest-timeout>=1.3.0",
        "pytest>=3.6.0",
    ],
}

all_require = []
for extra_require in extras_require.values():
    all_require.extend(extra_require)

extras_require["all"] = all_require


setup(
    python_requires="~=3.7",
    packages=find_packages(exclude=["test", "udev"]),
    data_files=[("lib/udev/rules", ["udev/69-glucometerutils.rules"]),],
    install_requires=["attrs",],
    extras_require=extras_require,
    entry_points={"console_scripts": ["glucometer=glucometerutils.glucometer:main"]},
)
