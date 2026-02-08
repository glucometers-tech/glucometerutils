# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2019 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines to implement the ContourUSB common protocol.

Protocol documentation available from Ascensia at
http://protocols.ascensia.com/Programming-Guide.aspx

* glucodump code segments are developed by Anders Hammarquist
* Rest of code is developed by Arvanitis Christos

"""

import datetime
import enum
import logging
import re
from collections.abc import Generator
from typing import Optional

from glucometerutils import driver
from glucometerutils.support import hiddevice

logger = logging.getLogger(__name__)

# regexr.com/4k6jb
_HEADER_RECORD_RE_USB = re.compile(
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
    "(?P<spec_ver>[0-9]+)\\|(?P<datetime>[0-9]+)"
)

_HEADER_RECORD_RE_NEXT = re.compile(
    "^(?P<record_type>[a-zA-Z])\\|(?P<field_del>.)(?P<repeat_del>.)"
    "(?P<component_del>.)(?P<escape_del>.)\\|\\w*\\|(?P<product_code>\\w+)"
    "\\^(?P<dig_ver>[0-9]{2}\\.[0-9]{2})\\\\(?P<anlg_ver>[0-9]{2}\\.[0-9]{2})"
    "\\\\(?P<agp_ver>[0-9]{2}\\.[0-9]{2})"
    "\\^(?P<serial_num>(\\w|-)+)\\|"
    "A=(?P<res_marking>[0-9])\\^C=(?P<config_bits>[0-9]+)\\^R=(?P<ref_method>[0-9]+)\\"
    "^S=(?P<internal>[0-9]+)\\^U=(?P<unit>[0-9]+)\\"
    "^V=(?P<lo_bound>[0-9]{2})(?P<hi_bound>[0-9]{3})\\"
    "^X=(?P<post_food_low>[0-9]{3})(?P<pre_food_low>[0-9]{3})"
    "(?P<post_food_high>[0-9]{3})(?P<pre_food_high>[0-9]{3})"
    "\\^a=(?P<a>[0-9])\\^J=(?P<J>[0-9])\\|"
    "(?P<total>[0-9]*)\\|\\|\\|\\|\\|(?P<unknown>[P])\\|"
    "(?P<spec_ver>[0-9]+)\\|(?P<datetime>[0-9]+)\\|"
)

_RESULT_RECORD_RE = re.compile(
    "^(?P<record_type>[a-zA-Z])\\|(?P<seq_num>[0-9]+)\\|\\w*\\^\\w*\\^\\w*\\"
    "^(?P<test_id>\\w+)\\|(?P<value>[0-9]+)\\|(?P<unit>\\w+\\/\\w+)\\^"
    "(?P<ref_method>[BPD])\\|\\|(?P<markers>[><BADISXCZT\\/0-12]*)\\|\\|"
    "(?P<datetime>[0-9]+)"
)

_RECORD_FORMAT = re.compile(
    "\x02(?P<check>(?P<recno>[0-7])(?P<text>[^\x0d]*)"
    "\x0d(?P<end>[\x03\x17]))"
    "(?P<checksum>[0-9A-F][0-9A-F])\x0d\x0a"
)


class FrameError(Exception):
    pass


@enum.unique
class Mode(enum.Enum):
    """Operation modes."""

    ESTABLISH = enum.auto()
    DATA = enum.auto()
    PRECOMMAND = enum.auto()
    COMMAND = enum.auto()


class ContourHidDevice(driver.GlucometerDevice):
    """Base class implementing the ContourUSB HID common protocol."""

    blocksize = 64

    state: Optional[Mode] = None

    currecno: Optional[int] = None

    def __init__(
        self,
        usb_ids: tuple[int, int],
        device_path: Optional[str],
        header_record_re: re.Pattern[str],
    ) -> None:
        super().__init__(device_path)
        self._hid_session = hiddevice.HidSession(usb_ids, device_path)
        self._header_record_re = header_record_re

    def read(self, r_size=blocksize):
        result = []

        while True:
            data = self._hid_session.read()
            dstr = data
            data_end_idx = data[3] + 4
            result.append(dstr[4:data_end_idx])
            if data[3] != self.blocksize - 4:
                break

        return b"".join(result)

    def write(self, data):
        data = b"ABC" + chr(len(data)).encode() + data.encode()
        pad_length = self.blocksize - len(data)
        data += pad_length * b"\x00"

        self._hid_session.write(data)

    def parse_header_record(self, text):
        header = self._header_record_re.search(text)
        if not header:
            raise FrameError("Couldn't parse header record", text)
        for key, value in header.groupdict().items():
            setattr(self, key, value)
        # Harmonize datetime string to YYYYMMDDHHMMSS format
        self.datetime = self.datetime.ljust(14, '0')

    def checksum(self, text):
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        checksum = hex(sum(ord(c) for c in text) % 256).upper().split("X")[1]
        return ("00" + checksum)[-2:]

    def checkframe(self, frame) -> Optional[str]:
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        match = _RECORD_FORMAT.match(frame)
        if not match:
            raise FrameError("Couldn't parse frame", frame)

        recno = int(match.group("recno"))
        if self.currecno is None:
            self.currecno = recno

        if recno + 1 == self.currecno:
            return None

        if recno != self.currecno:
            raise FrameError(
                f"Bad recno, got {recno!r} expected {self.currecno!r}", frame
            )

        calculated_checksum = self.checksum(match.group("check"))
        received_checksum = match.group("checksum")
        if calculated_checksum != received_checksum:
            raise FrameError(
                f"Checksum error: received {received_checksum} expected {calculated_checksum}",
                frame,
            )

        self.currecno = (self.currecno + 1) % 8
        return match.group("text")

    def connect(self):
        """Connecting the device, nothing to be done.
        All process is handled by hiddevice
        """
        pass

    def _get_info_record(self):
        self.currecno = None
        self.state = Mode.ESTABLISH
        try:
            while True:
                self.write("\x04")
                res = self.read()
                if res[0] == 4 and res[-1] == 5:
                    # we are connected and just got a header
                    header_record = res.decode()
                    stx = header_record.find("\x02")
                    if stx != -1:
                        result = _RECORD_FORMAT.match(header_record[stx:]).group("text")
                        self.parse_header_record(result)
                    break
                else:
                    pass

        except FrameError:
            logger.error("Frame error")
            raise

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

    # Some of the commands are also shared across devices that use this HID
    # protocol, but not many. Only provide here those that do seep to change
    # between them.
    def _get_version(self) -> str:
        """Return the software version of the device."""
        return self.dig_ver + " - " + self.anlg_ver + " - " + self.agp_ver

    def _get_serial_number(self) -> str:
        """Returns the serial number of the device."""
        return self.serial_num

    def _get_glucose_unit(self) -> str:
        """Return 0 for mg/dL, 1 for mmol/L"""
        return self.unit

    def get_datetime(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.datetime, '%Y%m%d%H%M%S')

    def sync(self) -> Generator[str, None, None]:
        """
        Sync with meter and yield received data frames
        FSM implemented by Anders Hammarquist's for glucodump
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        self.state = Mode.ESTABLISH
        tometer = "\x04"
        result = None
        foo = 0
        while True:
            self.write(tometer)
            if result is not None and self.state == Mode.DATA:
                yield result
            result = None
            data_bytes = self.read()
            data = data_bytes.decode()

            if self.state == Mode.ESTABLISH:
                if data_bytes[-1] == 15:
                    # got a <NAK>, send <EOT>
                    tometer = chr(foo)
                    foo += 1
                    foo %= 256
                    continue
                if data_bytes[-1] == 5:
                    # got an <ENQ>, send <ACK>
                    tometer = "\x06"
                    self.currecno = None
                    continue
            if self.state == Mode.DATA:
                if data_bytes[-1] == 4:
                    # got an <EOT>, done
                    self.state = Mode.PRECOMMAND
                    break
            stx = data.find("\x02")
            if stx != -1:
                # got <STX>, parse frame
                try:
                    result = self.checkframe(data[stx:])
                    if result == "L|1||N":
                        # got terminator record from Contour Next, send <EOT>
                        tometer = chr(foo)
                        foo += 1
                        foo %= 256
                        self.state = Mode.PRECOMMAND
                        break
                    else:
                        tometer = "\x06"
                        self.state = Mode.DATA
                except FrameError:
                    tometer = "\x15"  # Couldn't parse, <NAK>
            else:
                # Got something we don't understand, <NAK> it
                tometer = "\x15"

    def parse_result_record(self, text: str) -> dict[str, str]:
        result = _RESULT_RECORD_RE.search(text)
        assert result is not None
        rec_text = result.groupdict()
        return rec_text

    def _get_multirecord(self) -> list[dict[str, str]]:
        """Queries for, and returns, "multirecords" results.

        Returns:
          (csv.reader): a CSV reader object that returns a record for each line
             in the record file.
        """
        records_arr = []
        for rec in self.sync():
            if rec[0] == "R":
                # parse using result record regular expression
                rec_text = self.parse_result_record(rec)
                # get dictionary to use in main driver module without import re

                records_arr.append(rec_text)
        # return csv.reader(records_arr)
        return records_arr  # array of groupdicts
