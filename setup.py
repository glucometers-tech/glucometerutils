# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT

import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


with open('test-requirements.txt') as requirements:
    test_required = requirements.read().splitlines()


class PyTestCommand(TestCommand):

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main([])
        sys.exit(errno)


setup(
    name = 'glucometerutils',
    version = '1',
    description = 'Glucometer access utilities',
    author = 'Diego Elio Pettenò',
    author_email = 'flameeyes@flameeyes.com',
    url = 'https://www.flameeyes.com/p/glucometerutils',
    download_url = 'https://www.flameeyes.com/files/glucometerutils.tgz',
    keywords = ['glucometer', 'diabetes'],
    python_requires = '~=3.5',
    classifiers = [
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Scientific/Engineering :: Medical Science Apps.',
    ],
    packages = find_packages(
        exclude=['test', 'udev']),
    data_files = [
        ('lib/udev/rules', ['udev/69-glucometerutils.rules']),
    ],
    install_requires = [
        'attrs',
    ],
    tests_require = test_required,
    extras_require = {
        # These are all the drivers' dependencies. Optional dependencies are
        # listed as mandatory for the feature.
        'accucheck_reports': [],
        'contourusb': ['construct', 'hidapi'],
        'fsinsulinx': ['construct', 'hidapi'],
        'fslibre': ['construct', 'hidapi'],
        'fsoptium': ['pyserial'],
        'fsprecisionneo': ['construct', 'hidapi'],
        'otultra2': ['pyserial'],
        'otultraeasy': ['construct', 'pyserial'],
        'otverio2015': ['construct', 'python-scsi'],
        'otverioiq': ['construct', 'pyserial'],
        'sdcodefree': ['construct', 'pyserial'],
        'td4277': ['construct', 'pyserial', 'hidapi'],
    },
    entry_points = {
        'console_scripts': [
            'glucometer=glucometerutils.glucometer:main'
        ]
    },
    cmdclass = {
        'test': PyTestCommand,
    },
)
