# -*- coding: utf-8 -*-

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
    author_email = 'flameeyes@flameeyes.eu',
    url = 'https://www.flameeyes.eu/p/glucometerutils',
    download_url = 'https://www.flameeyes.eu/files/glucometerutils.tgz',
    keywords = ['glucometer', 'diabetes'],
    python_requires = '~=3.4',
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
    tests_require = test_required,
    extras_require = {
        # These are all the drivers' dependencies. Optional dependencies are
        # listed as mandatory for the feature.
        'otultra2': ['pyserial'],
        'otultraeasy': ['pyserial'],
        'otverio2015': ['python-scsi'],
        'fsinsulinx': ['construct', 'hidapi'],
        'fslibre': ['construct', 'hidapi'],
        'fsoptium': ['pyserial'],
        'fsprecisionneo': ['construct', 'hidapi'],
        'accucheck_reports': [],
        'sdcodefree': ['construct', 'pyserial'],
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
