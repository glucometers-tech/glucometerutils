# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Extra classes for Construct."""

import datetime

import construct

class Timestamp(construct.Adapter):
    """Adapter for converting datetime object into timestamps.

    Take two parameters: the subcon object to output the resulting timestamp as,
    and an optional epoch offset to the UNIX Epoch.

    """
    __slots__ = ["epoch"]

    def __init__(self, subcon, epoch=0):
        super(Timestamp, self).__init__(subcon)
        self.epoch = epoch

    def _encode(self, obj, context, path):
        assert isinstance(obj, datetime.datetime)
        epoch_date = datetime.datetime.utcfromtimestamp(self.epoch)
        delta = obj - epoch_date
        return int(delta.total_seconds())

    def _decode(self, obj, context, path):
        return datetime.datetime.utcfromtimestamp(obj + self.epoch)
