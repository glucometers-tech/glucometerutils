# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT

from setuptools import setup

# Ensure it's present.
import setuptools_scm  # noqa: F401

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
    "otverio2015": ["construct", "PYSCSI[sgio]>=2.0.1"],
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
        "pytest-flake8",
        "pytest-mypy",
        "pytest-timeout>=1.3.0",
        "pytest>=3.6.0",
    ],
}

all_require = []
for extra_require in extras_require.values():
    all_require.extend(extra_require)

extras_require["all"] = all_require


setup(
    extras_require=extras_require,
    entry_points={"console_scripts": ["glucometer=glucometerutils.glucometer:main"]},
)
