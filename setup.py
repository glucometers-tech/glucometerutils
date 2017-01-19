# -*- coding: utf-8 -*-

from distutils.core import setup

setup(
  name = 'glucometerutils',
  packages = ['glucometerutils', 'glucometerutils.drivers', 'glucometerutils.support'],
  scripts = ['glucometer.py'],
  version = '1',
  description = 'Glucometer access utilities',
  author = 'Diego Elio Pettenò',
  author_email = 'flameeyes@flameeyes.eu',
  url = 'https://www.flameeyes.eu/projects/glucometerutils',
  download_url = 'https://www.flameeyes.eu/files/glucometerutils.tgz',
  keywords = ['glucometer', 'diabetes'],
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
)
