# -*- coding: utf-8 -*-
"""Add the top-level module to the PYTHONPATH."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.com'
__copyright__ = 'Copyright © 2018, Diego Elio Pettenò'
__license__ = 'MIT'

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
