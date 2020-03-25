# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT

import sys

from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

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
}

tests_require = [
    "absl-py",
    "construct>=2.9",
    "pytest>=3.6.0",
    "pytest-timeout>=1.3.0",
]

# Development and testing dependencies
extras_require["dev"] = tests_require + ["pre-commit", "mypy"]

all_require = []
for extra_require in extras_require.values():
    all_require.extend(extra_require)

tests_require.extend(all_require)
extras_require["all"] = all_require


class PyTestCommand(TestCommand):
    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest

        errno = pytest.main([])
        sys.exit(errno)


setup(
    python_requires="~=3.7",
    packages=find_packages(exclude=["test", "udev"]),
    data_files=[("lib/udev/rules", ["udev/69-glucometerutils.rules"]),],
    install_requires=["attrs",],
    tests_require=tests_require,
    extras_require=extras_require,
    entry_points={"console_scripts": ["glucometer=glucometerutils.glucometer:main"]},
    cmdclass={"test": PyTestCommand,},
)
