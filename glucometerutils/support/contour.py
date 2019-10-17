# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Common routines to implement the Contour Next One common protocol.

Protocol documentation available from Ascensia at
http://protocols.ascensia.com/Programming-Guide.aspx

* glucodump code segments are developed by Anders Hammarquist
* Rest of code is developed by Arvanitis Christos

"""

import csv
import datetime
import logging
import re
import construct

from glucometerutils import exceptions
from glucometerutils.exceptions import InvalidResponse
from glucometerutils.support import hiddevice


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
        match = self._RECORD_FORMAT.match(frame)
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

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

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
            (int(datetime_str[12:14]) if len(datetime_str) == 14 else 0)
            )

    def _get_info_record(self):
        self.currecno = None
        self.state = self.mode_establish
        try:
            while True:
                self.write(self.EOT)  # any char except ACK and NAK
                res = self.read()
                if res[0] == 4 and res[-1] == 5:
                    # we are connected and just got a header
                    header_record = res.decode()
                    stx = header_record.find(self.STX)
                    if stx != -1:
                        result = self._RECORD_FORMAT.match(
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

    def parse_result_record(self, text):
        # type : text -> dict
        result = self._RESULT_RECORD_RE.search(text)
        rec_text = result.groupdict()
        return rec_text

    def _get_multirecord(self):
        # type: (bytes) -> Iterator[List[Text]]
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
