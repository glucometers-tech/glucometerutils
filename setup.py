# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

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
    extras_require = {
        'test': ['abseil-py'],
    },
    entry_points = {
        'console_scripts': [
            'glucometer=glucometerutils.glucometer:main'
        ]
    },
)
