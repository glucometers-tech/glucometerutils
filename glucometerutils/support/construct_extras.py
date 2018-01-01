# -*- coding: utf-8 -*-
"""Extra classes for Construct."""

__author__ = 'Diego Elio Pettenò'
__email__ = 'flameeyes@flameeyes.eu'
__copyright__ = 'Copyright © 2018, Diego Elio Pettenò'
__license__ = 'MIT'

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

    def _encode(self, obj, context):
        assert isinstance(obj, datetime.datetime)
        epoch_date = datetime.datetime.utcfromtimestamp(self.epoch)
        delta = obj - epoch_date
        return int(delta.total_seconds())

    def _decode(self, obj, context):
        return datetime.datetime.utcfromtimestamp(obj + self.epoch)
