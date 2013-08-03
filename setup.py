from distutils.core import setup

setup(
  name = 'glucometerutils',
  packages = ['glucometerutils', 'glucometerutils.drivers'],
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
    'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    'Intended Audience :: End Users/Desktop',
    'Topic :: Scientific/Engineering :: Medical Science Apps.',
  ],
)
