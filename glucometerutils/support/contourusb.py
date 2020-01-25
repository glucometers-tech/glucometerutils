# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines to implement the ContourUSB common protocol.

Protocol documentation available from Ascensia at
http://protocols.ascensia.com/Programming-Guide.aspx

* glucodump code segments are developed by Anders Hammarquist
* Rest of code is developed by Arvanitis Christos

"""

import csv
import datetime
import logging
import re
from typing import Dict, Iterator, List, Text

import construct

from glucometerutils import exceptions
from glucometerutils.exceptions import InvalidResponse
from glucometerutils.support import hiddevice

# regexr.com/4k6jb
_HEADER_RECORD_RE = re.compile(
    "^(?P<record_type>[a-zA-Z])\\|(?P<field_del>.)(?P<repeat_del>.)"
    "(?P<component_del>.)(?P<escape_del>.)\\|\\w*\\|(?P<product_code>\\w+)"
    "\\^(?P<dig_ver>[0-9]{2}\\.[0-9]{2})\\\\(?P<anlg_ver>[0-9]{2}\\.[0-9]{2})"
    "\\\\(?P<agp_ver>[0-9]{2}\\.[0-9]{2}\\.[0-9]{2})\\"
    "^(?P<serial_num>(\\w|-)+)\\^(?P<sku_id>(\\w|-)+)\\|"
    "A=(?P<res_marking>[0-9])\\^C=(?P<config_bits>[0-9]+)\\"
    "^G=(?P<lang>[0-9]+)\\^I=(?P<interv>[0-9]+)\\^R=(?P<ref_method>[0-9]+)\\"
    "^S=(?P<internal>[0-9]+)\\^U=(?P<unit>[0-9]+)\\"
    "^V=(?P<lo_bound>[0-9]{2})(?P<hi_bound>[0-9]{3})\\"
    "^X=(?P<hypo_limit>[0-9]{3})(?P<overall_low>[0-9]{3})"
    "(?P<pre_food_low>[0-9]{3})(?P<post_food_low>[0-9]{3})"
    "(?P<overall_high>[0-9]{3})(?P<pre_food_high>[0-9]{3})"
    "(?P<post_food_high>[0-9]{3})(?P<hyper_limit>[0-9]{3})\\"
    "^Y=(?P<upp_hyper>[0-9]{3})(?P<low_hyper>[0-9]{3})"
    "(?P<upp_hypo>[0-9]{3})(?P<low_hypo>[0-9]{3})(?P<upp_low_target>[0-9]{3})"
    "(?P<low_low_target>[0-9]{3})(?P<upp_hi_target>[0-9]{3})"
    "(?P<low_hi_target>[0-9]{3})\\^Z=(?P<trends>[0-2])\\|"
    "(?P<total>[0-9]*)\\|\\|\\|\\|\\|\\|"
    "(?P<spec_ver>[0-9]+)\\|(?P<datetime>[0-9]+)")

_RESULT_RECORD_RE = re.compile(
    "^(?P<record_type>[a-zA-Z])\\|(?P<seq_num>[0-9]+)\\|\\w*\\^\\w*\\^\\w*\\"
    "^(?P<test_id>\\w+)\\|(?P<value>[0-9]+)\\|(?P<unit>\\w+\\/\\w+)\\^"
    "(?P<ref_method>[BPD])\\|\\|(?P<markers>[><BADISXCZ\\/1-12]*)\\|\\|"
    "(?P<datetime>[0-9]+)")

_RECORD_FORMAT = re.compile(
    '\x02(?P<check>(?P<recno>[0-7])(?P<text>[^\x0d]*)'
    '\x0d(?P<end>[\x03\x17]))'
    '(?P<checksum>[0-9A-F][0-9A-F])\x0d\x0a')

class FrameError(Exception):
    pass

class ContourHidDevice(hiddevice.HidDevice):
    """Base class implementing the ContourUSB HID common protocol.
    """
    blocksize = 64

    # Operation modes
    mode_establish = object
    mode_data = object()
    mode_precommand = object()
    mode_command = object()
    state = None

    def read(self, r_size=blocksize):
        result = []

        while True:
            data = self._read()
            dstr = data
            result.append(dstr[4:data[3]+4])
            if data[3] != self.blocksize-4:
                break

        return (b"".join(result))

    def write(self, data):
        data = b'ABC' + chr(len(data)).encode() + data.encode()
        pad_length = self.blocksize - len(data)
        data += pad_length * b'\x00'

        self._write(data)

    USB_VENDOR_ID = 0x1a79  # type: int  # Bayer Health Care LLC Contour
    USB_PRODUCT_ID = 0x6002  # type: int

    def parse_header_record(self, text):
        header = _HEADER_RECORD_RE.search(text)

        self.field_del = header.group('field_del')
        self.repeat_del = header.group('repeat_del')
        self.component_del = header.group('component_del')
        self.escape_del = header.group('escape_del')

        self.product_code = header.group('product_code')
        self.dig_ver = header.group('dig_ver')
        self.anlg_ver = header.group('anlg_ver')
        self.agp_ver = header.group('agp_ver')

        self.serial_num = header.group('serial_num')
        self.sku_id = header.group('sku_id')
        self.res_marking = header.group('res_marking')
        self.config_bits = header.group('config_bits')
        self.lang = header.group('lang')
        self.interv = header.group('interv')
        self.ref_method = header.group('ref_method')
        self.internal = header.group('internal')

        # U limit
        self.unit = header.group('unit')
        self.lo_bound = header.group('lo_bound')
        self.hi_bound = header.group('hi_bound')

        # X field
        self.hypo_limit = header.group('hypo_limit')
        self.overall_low = header.group('overall_low')
        self.pre_food_low = header.group('pre_food_low')
        self.post_food_low = header.group('post_food_low')
        self.overall_high = header.group('overall_high')
        self.pre_food_high = header.group('pre_food_high')
        self.post_food_high = header.group('post_food_high')
        self.hyper_limit = header.group('hyper_limit')

        # Y field
        self.upp_hyper = header.group('upp_hyper')
        self.low_hyper = header.group('low_hyper')
        self.upp_hypo = header.group('upp_hypo')
        self.low_hypo = header.group('low_hypo')
        self.upp_low_target = header.group('upp_low_target')
        self.low_low_target = header.group('low_low_target')
        self.upp_hi_target = header.group('upp_hi_target')
        self.low_hi_target = header.group('low_hi_target')

        # Z field
        self.trends = header.group('trends')

        self.total = header.group('total')
        self.spec_ver = header.group('spec_ver')
        # Datetime string in YYYYMMDDHHMM format
        self.datetime = header.group('datetime')


    def checksum(self, text):
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        checksum = hex(sum(ord(c) for c in text) % 256).upper().split('X')[1]
        return ('00' + checksum)[-2:]

    def checkframe(self, frame):
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        match = _RECORD_FORMAT.match(frame)
        if not match:
            raise FrameError("Couldn't parse frame", frame)

        recno = int(match.group('recno'))
        if self.currecno is None:
            self.currecno = recno

        if recno + 1 == self.currecno:
            return None

        if recno != self.currecno:
            raise FrameError("Bad recno, got %r expected %r" %
                             (recno, self.currecno),
                             frame)

        checksum = self.checksum(match.group('check'))
        if checksum != match.group('checksum'):
            raise FrameError("Checksum error: got %s expected %s" %
                             (match.group('checksum'), checksum),
                             frame)

        self.currecno = (self.currecno + 1) % 8
        return match.group('text')

    def connect(self):
        """Connecting the device, nothing to be done.
        All process is hadled by hiddevice
        """
        pass

    def _get_info_record(self):
        self.currecno = None
        self.state = self.mode_establish
        try:
            while True:
                self.write('\x04')
                res = self.read()
                if res[0] == 4 and res[-1] == 5:
                    # we are connected and just got a header
                    header_record = res.decode()
                    stx = header_record.find('\x02')
                    if stx != -1:
                        result = _RECORD_FORMAT.match(
                            header_record[stx:]).group('text')
                        self.parse_header_record(result)
                    break
                else:
                    pass

        except FrameError as e:
            print("Frame error")
            raise e

        except Exception as e:
            print("Uknown error occured")
            raise e

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

    # Some of the commands are also shared across devices that use this HID
    # protocol, but not many. Only provide here those that do seep to change
    # between them.
    def _get_version(self):
        # type: () -> Text
        """Return the software version of the device."""
        return self.dig_ver + " - " + self.anlg_ver + " - " + self.agp_ver

    def _get_serial_number(self):
        # type: () -> Text
        """Returns the serial number of the device."""
        return self.serial_num

    def _get_glucose_unit(self):
        # type: () -> Text
        """Return 0 for mg/dL, 1 for mmol/L"""
        return self.unit

    def get_datetime(self):
        # type: () -> datetime.datetime
        datetime_str = self.datetime
        return datetime.datetime(
            int(datetime_str[0:4]),  # year
            int(datetime_str[4:6]),  # month
            int(datetime_str[6:8]),  # day
            int(datetime_str[8:10]),  # hour
            int(datetime_str[10:12]),  # minute
            0)

    def sync(self):
        """
        Sync with meter and yield received data frames
        FSM implemented by Anders Hammarquist's for glucodump
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        self.state = self.mode_establish
        try:
            tometer = '\x04'
            result = None
            foo = 0
            while True:
                self.write(tometer)
                if result is not None and self.state == self.mode_data:
                    yield result
                result = None
                data_bytes = self.read()
                data = data_bytes.decode()

                if self.state == self.mode_establish:
                    if data_bytes[-1] == 15:
                        # got a <NAK>, send <EOT>
                        tometer = chr(foo)
                        foo += 1
                        foo %= 256
                        continue
                    if data_bytes[-1] == 5:
                        # got an <ENQ>, send <ACK>
                        tometer = '\x06'
                        self.currecno = None
                        continue
                if self.state == self.mode_data:
                    if data_bytes[-1] == 4:
                        # got an <EOT>, done
                        self.state = self.mode_precommand
                        break
                stx = data.find('\x02')
                if stx != -1:
                    # got <STX>, parse frame
                    try:
                        result = self.checkframe(data[stx:])
                        tometer = '\x06'
                        self.state = self.mode_data
                    except FrameError as e:
                        tometer = '\x15'  # Couldn't parse, <NAK>
                else:
                    # Got something we don't understand, <NAK> it
                    tometer = '\x15'
        except Exception as e:
            raise e

    def parse_result_record(self, text):
        # type: (Text) -> Dict[Text, Text]
        result = _RESULT_RECORD_RE.search(text)
        assert result is not None
        rec_text = result.groupdict()
        return rec_text

    def _get_multirecord(self):
        # type: () -> List[Dict[Text, Text]]
        """Queries for, and returns, "multirecords" results.

        Returns:
          (csv.reader): a CSV reader object that returns a record for each line
             in the record file.
        """
        records_arr = []
        for rec in self.sync():
            if rec[0] == 'R':
                # parse using result record regular expression
                rec_text = self.parse_result_record(rec)
                # get dictionary to use in main driver module without import re

                records_arr.append(rec_text)
        # return csv.reader(records_arr)
        return records_arr  # array of groupdicts
