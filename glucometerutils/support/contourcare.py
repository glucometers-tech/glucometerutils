# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2026 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Common routines to implement communication with Contour Care devices.

The communication is fairly similar to ContourUSB devices, but slightly different in a few places.
Since there is no official protocol document available

* glucodump code segments are developed by Anders Hammarquist
* code for the contourusb driver was developed by Arvanitis Christos
* additional edits by Lorenz Gillner
"""

import datetime
import enum
import re
from collections.abc import Generator
from typing import Optional

from glucometerutils import driver
from glucometerutils.support import hiddevice

_RECORD_FORMAT_RE = re.compile(
    r"\x02(?P<check>(?P<recno>[0-7])(?P<text>[^\x0d]*)\x0d(?P<end>[\x17\x03]))"
    r"(?P<checksum>[0-9A-F][0-9A-F])\x0d\x0a"
)

_HEADER_RECORD_RE = re.compile(
    r"H\|\\\^\&\|\|"  # repeat, component, escape, field
    r"(?P<session_id>\w{6})\|"
    r"(?P<product_code>\w+)\^"
    r"(?P<dig_ver>\d{2}\.\d{2})\\"
    r"(?P<anlg_ver>\d{2}\.\d{2})\\"
    r"(?P<agp_ver>\d{2}\.\d{2})\^"
    r"(?P<serial_num>\w+)\|"
    r"A=(?P<res_marking>\d)\^"
    r"C=(?P<config_bits>\d+)\^"
    r"R=(?P<ref_method>\d+)\^"
    r"S=(?P<internal>\d+)\^"
    r"U=(?P<unit>\d+)\^"
    r"V=(?P<lo_bound>\d{2})(?P<hi_bound>\d{3})\^"
    r"X=(?P<post_food_low>\d{3})(?P<pre_food_low>\d{3})"
    r"(?P<post_food_high>\d{3})(?P<pre_food_high>\d{3})\^"
    r"a=(?P<unclear>\d+)\^"
    r"J=(?P<dont_know>\d+)\|"
    r"(?P<total_recs>\d*)\|\|\|\|\|"
    r"[DPT]\|(?P<proto>\d+)\|"
    r"(?P<datetime>\d+)\|"
)

_RESULT_RECORD_RE = re.compile(
    r"R\|(?P<seqnum>\d+)\|"
    r"\^\^\^Glucose\|"
    r"(?P<value>\d+\.\d+)\|"
    r"(?P<unit>\w+\/\w+)\^(?P<ref_method>[BPD])\|\|"
    r"(?P<meal>(\w+\/)?\w+)\|\|"
    r"(?P<datetime>\d+)"
)

_PATIENT_RECORD_RE = re.compile(r"P\|(?P<seqnum>\d+)\|")

_TERMINATOR_RECORD_RE = re.compile(r"L\|1\|\|(?P<code>[NTERQIF]?)")

VENDOR_ID: int = 0x1A79  # Bayer Health Care LLC
TIMEOUT_MS: int = 200


class FrameError(Exception):
    pass


@enum.unique
class Control(enum.IntEnum):
    """ASCII Control characters."""

    PAD = 0x00
    STX = 0x02
    ETX = 0x03
    EOT = 0x04
    ENQ = 0x05
    ACK = 0x06
    NAK = 0x15
    ETB = 0x17
    WAK = 0x58


@enum.unique
class TerminatorCode(enum.Enum):
    """Terminator record return codes."""

    NORMAL = "N"
    SENDER_ABORT = "T"
    RECEIVER_ABORT = "R"
    UNKNOWN = "E"
    REQUEST_ERROR = "Q"
    NO_INFORMATION = "I"
    LAST_REQUEST = "F"


@enum.unique
class Mode(enum.Enum):
    """Operation modes."""

    ESTABLISH = enum.auto()
    DATA = enum.auto()
    PRECOMMAND = enum.auto()
    COMMAND = enum.auto()


class ContourCareHidDevice(driver.GlucometerDevice):
    """Base class implementing the Contour Care device."""

    blocksize: int = 64
    state: Optional[Mode] = None
    currecno: Optional[int] = None

    def __init__(self, product_id: int, device_path: Optional[str]) -> None:
        super().__init__(device_path)
        hidid = (VENDOR_ID, product_id)
        self._hid_session = hiddevice.HidSession(hidid, device_path, TIMEOUT_MS)

    def connect(self):
        """Connect to the device; handled by `hiddevice`."""
        pass

    def disconnect(self):
        """Disconnect from the device; handled by `hiddevice`."""
        pass

    def read(self, r_size=blocksize) -> bytes:
        """Read data via `hiddevice`."""
        result = bytes()

        while True:
            data = self._hid_session.read()
            data_end_idx = data[3] + 4
            result += data[4:data_end_idx]

            # Data is smaller than block size; must be the last block
            if data[3] != self.blocksize - 4:
                break

        return result

    def write(self, message: Control) -> None:
        pad = bytes([Control.PAD])
        data = 4 * pad
        data += chr(1).encode()
        data += bytes([message])
        pad_length = self.blocksize - len(data)
        data += pad_length * pad
        self._hid_session.write(data)

    def checksum(self, text):
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        checksum = hex(sum(ord(c) for c in text) % 256).upper().split("X")[1]
        return ("00" + checksum)[-2:]

    def checkframe(self, frame: str) -> Optional[str]:
        """
        Implemented by Anders Hammarquist for glucodump project
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        match = _RECORD_FORMAT_RE.match(frame)

        if match is None:
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

    def parse_header_record(self, text: str) -> None:
        """Parse a header record and set device properties."""
        header = _HEADER_RECORD_RE.search(text)
        assert header is not None

        self.product_code = header.group("product_code")
        self.dig_ver = header.group("dig_ver")
        self.anlg_ver = header.group("anlg_ver")
        self.agp_ver = header.group("agp_ver")

        self.serial_num = header.group("serial_num")
        self.res_marking = header.group("res_marking")
        self.config_bits = header.group("config_bits")
        self.ref_method = header.group("ref_method")
        self.internal = header.group("internal")

        # U limit
        self.unit = header.group("unit")
        self.lo_bound = header.group("lo_bound")
        self.hi_bound = header.group("hi_bound")

        # X field
        self.post_food_low = header.group("post_food_low")
        self.pre_food_low = header.group("pre_food_low")
        self.post_food_high = header.group("post_food_high")
        self.pre_food_high = header.group("pre_food_high")

        self.total = header.group("total_recs")

        # Datetime string in YYYYMMDDHHMMSS format
        self.datetime = header.group("datetime")

    def parse_result_record(self, text: str) -> dict[str, str]:
        """Parse a result record and return it as a dictionary."""
        result = _RESULT_RECORD_RE.search(text)
        assert result is not None
        return result.groupdict()

    def parse_terminator_record(self, text: str) -> TerminatorCode:
        """Parse a terminator record and return it as a dictionary."""
        result = _TERMINATOR_RECORD_RE.search(text)
        assert result is not None
        return TerminatorCode(result.group("code"))

    def parse_timestamp(self, datetime_str: str) -> datetime.datetime:
        """Extract the timestamp from a parsed record."""
        return datetime.datetime(
            int(datetime_str[0:4]),  # year
            int(datetime_str[4:6]),  # month
            int(datetime_str[6:8]),  # day
            int(datetime_str[8:10]),  # hour
            int(datetime_str[10:12]),  # minute
            int(datetime_str[12:14]),  # second
            0,
        )

    def _get_info_record(self) -> None:
        self.currecno = None
        self.state = Mode.ESTABLISH

        try:
            while True:
                # Send EOT to suppress further output; device will answer with a header anyway
                self.write(Control.EOT)
                res = self.read()

                if res[0] == Control.EOT and res[-1] == Control.ENQ:
                    # We are connected and just got a header
                    stx = res.find(Control.STX)
                    if stx != -1:
                        header_record = res[stx:-1].decode()
                        result = _RECORD_FORMAT_RE.match(header_record)
                        assert result is not None
                        self.parse_header_record(result.group("text"))

                    break
                else:
                    pass

        except FrameError as e:
            print("Frame error")
            raise e

        except Exception as e:
            print("Unknown error occured")
            raise e

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
        return self.parse_timestamp(self.datetime)

    def sync(self) -> Generator[str, None, None]:
        """Sync with meter and yield received data frames."""
        self.state = Mode.ESTABLISH

        try:
            # Send "wake up call"
            self.write(Control.WAK)

            tometer = Control.ACK
            result = None

            # Repeat until all records have been sent
            while True:
                self.write(tometer)

                # If we are in transmission mode, yield data
                if result is not None and self.state == Mode.DATA:
                    yield result

                result = None
                data = self.read()

                if self.state == Mode.ESTABLISH:
                    match data[-1]:
                        case Control.NAK:
                            # Got a <NAK>, send <EOT>
                            tometer = Control.EOT
                            continue

                        case Control.ENQ:
                            # Got an <ENQ>, send <ACK>
                            tometer = Control.ACK
                            self.currecno = None
                            continue

                if self.state == Mode.DATA:
                    if data[-5] == Control.ETX:
                        self.state = Mode.PRECOMMAND
                        tometer = Control.EOT
                        break

                # Search for start of frame
                stx = data.find(Control.STX)

                if stx != -1:
                    # Got <STX>, parse frame
                    try:
                        frame = bytes.decode(data[stx:])
                        result = self.checkframe(frame)
                        tometer = Control.ACK
                        self.state = Mode.DATA
                    except FrameError:
                        tometer = Control.NAK  # Couldn't parse, send <NAK>
                else:
                    # Got something we don't understand, <NAK> it
                    tometer = Control.NAK

        except Exception as e:
            raise e

    def _get_multirecord(self) -> list[dict[str, str]]:
        """Queries for, and returns, "multirecords" results.

        Returns:
          A list of dictionaries, each representing a record from the record file.
        """
        records = []

        for rec in self.sync():
            match rec[0]:
                case "R":
                    record = self.parse_result_record(rec)
                    records.append(record)
                case "L":
                    code = self.parse_terminator_record(rec)
                    if code != TerminatorCode.NORMAL:
                        raise ValueError(f"Unexpected terminator code: {code}")
                    break
                case _:
                    continue

        return records  # array of groupdicts
