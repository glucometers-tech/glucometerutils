# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Add the top-level module to the PYTHONPATH."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
