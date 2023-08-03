# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT

# Ensure it's present.
import setuptools_scm  # noqa: F401
from setuptools import setup

extras_require = {
    # These are all the drivers' dependencies. Optional dependencies are
    # listed as mandatory for the feature.
    "accucheck_reports": [],
    "contourusb": ["construct", "hidapi"],
    "fsfreedomlite": ["pyserial"],
    "fsinsulinx": ["freestyle-hid>=1.0.2"],
    "fslibre": ["freestyle-hid>=1.0.2"],
    "fslibre2": ["freestyle-hid[encryption]>=1.1.0"],
    "fsoptium": ["pyserial"],
    "fsprecisionneo": ["freestyle-hid>=1.0.2"],
    "glucomenareo": ["pyserial", "crcmod"],
    "otultra2": ["pyserial"],
    "otultraeasy": ["construct", "pyserial"],
    "otverio2015": ["construct", "PYSCSI[sgio]>=2.0.1"],
    "otverioiq": ["construct", "pyserial"],
    "sdcodefree": ["construct", "pyserial"],
    "td42xx": ["construct", "pyserial[cp2110]>=3.5b0"],
    "dev": [
        "absl-py",
        "construct>=2.9",
        "mypy",
        "pre-commit",
        "pytest-mypy",
        "pytest-timeout>=1.3.0",
        "pytest>=3.6.0",
        "types-python-dateutil",
    ],
}

all_require = []
for extra_require in extras_require.values():
    all_require.extend(extra_require)

extras_require["all"] = all_require


setup(
    extras_require=extras_require,
)
