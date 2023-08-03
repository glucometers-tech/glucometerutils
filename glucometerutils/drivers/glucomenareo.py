# SPDX-FileCopyrightText: © 2021 The glucometerutils Authors
# SPDX-License-Identifier: MIT

"""Driver for GlucoMen Areo devices.

Supported features:
    - get readings, including pre-/post-meal notes and comments;
    - set date and time.

Expected device path: /dev/ttyUSB0 or similar serial port device.
"""

import dataclasses
import datetime
import logging
from collections.abc import Generator, Iterator, Mapping, Sequence
from typing import NoReturn, Union

import crcmod.predefined
import serial as pyserial

from glucometerutils import common, driver, exceptions
from glucometerutils.support import serial

_crc8_maxim = crcmod.predefined.mkPredefinedCrcFun("crc-8-maxim")

_CMD_GET_INFO = b"\xa2"

_CMD_SET_DATETIME = b"\xc2\xa1"

_CMD_GET_READINGS = b"\x80"

_UNITS_MAPPING = {
    "mmol/L": common.Unit.MMOL_L,
    "mg/dL": common.Unit.MG_DL,
}

_MARKINGS_MAPPING: Mapping[str, Union[str, common.Meal]] = {
    "00": "",
    "01": "Check Mark",
    "02": common.Meal.BEFORE,
    "04": common.Meal.AFTER,
    "08": "Exercise",
}


@dataclasses.dataclass(frozen=True)
class _Reading:
    reading_type: str
    value_string: str
    unit_string: str
    marking_string: str
    date: str
    time: str

    @property
    def value(self) -> float:
        return float(self.value_string)

    @property
    def unit(self) -> common.Unit:
        return _UNITS_MAPPING[self.unit_string]

    @property
    def _marking(self) -> Union[str, common.Meal]:
        return _MARKINGS_MAPPING[self.marking_string]

    @property
    def meal(self) -> common.Meal:
        if isinstance(self._marking, common.Meal):
            return self._marking
        else:
            return common.Meal.NONE

    @property
    def comment(self) -> str:
        if not isinstance(self._marking, common.Meal):
            return self._marking
        else:
            return ""

    @property
    def timestamp(self) -> datetime.datetime:
        return datetime.datetime.strptime(f"{self.date},{self.time}", "%y%m%d,%H%M")


class Device(serial.SerialDevice, driver.GlucometerDevice):
    BAUDRATE = 9600
    PARITY = pyserial.PARITY_ODD
    DEFAULT_CABLE_ID = "10c4:ea60"  # Generic cable.

    def connect(self) -> None:  # pylint: disable=no-self-use
        pass

    def disconnect(self) -> None:  # pylint: disable=no-self-use
        pass

    def _readline(self) -> bytes:
        line = self.serial_.readline()
        logging.debug(f"Read line: {line!r}")
        return line

    def _read_text_response(self) -> Sequence[bytes]:
        all_lines: list[bytes] = []

        while True:
            line = self._readline()
            if not line.endswith(b"\r\n"):
                raise exceptions.InvalidResponse(f"Corrupted response line: {line!r}")
            all_lines.append(line)

            if line == b"]\r\n":
                break

        if all_lines[0] != b"[\r\n":
            raise exceptions.InvalidResponse(
                f"Unexpected first response line: {all_lines!r}"
            )

        wire_checksum = int(all_lines[-2][:-2], base=16)
        calculated_checksum = _crc8_maxim(b"".join(all_lines[:-2]))

        if wire_checksum != calculated_checksum:
            raise exceptions.InvalidChecksum(wire_checksum, calculated_checksum)

        return [line[:-2] for line in all_lines[1:-2]]

    def _send_command(self, command: bytes) -> None:
        logging.debug(f"sending command: {command!r}")
        self.serial_.write(command)

    def _get_meter_info(self) -> Sequence[str]:
        self._send_command(_CMD_GET_INFO)
        get_info_response = list(self._read_text_response())
        if len(get_info_response) != 1:
            raise exceptions.InvalidResponse(
                f"Multiple lines returned, when one expected: {get_info_response!r}"
            )
        info = get_info_response[0].split(b",")
        if len(info) != 5:
            raise exceptions.InvalidResponse(
                f"Incomplete information response received: {get_info_response!r}"
            )

        return [component.decode("ascii") for component in info]

    def get_serial_number(self) -> str:
        return self._get_meter_info()[3].strip()

    def get_version_info(self) -> Sequence[str]:
        info = self._get_meter_info()
        return (info[4].strip(),)

    def get_meter_info(self) -> common.MeterInfo:
        return common.MeterInfo(
            "GlucoMen areo",
            serial_number=self.get_serial_number(),
            version_info=self.get_version_info(),
            native_unit=self.get_glucose_unit(),
        )

    def get_datetime(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def zero_log(self) -> NoReturn:
        raise NotImplementedError

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        datetime_representation = date.strftime("%y%m%d%H%M").encode("ascii")
        command_string = b"[\r\n" + datetime_representation + b"\r\n"

        checksum = _crc8_maxim(command_string)
        assert 0 <= checksum <= 255

        command_string += f"{checksum:02X}".encode("ascii") + b"\r\n]\r\n"

        command = _CMD_SET_DATETIME + command_string
        self._send_command(command)
        response = self.serial_.read()
        if response == b"P":
            return date
        else:
            raise exceptions.InvalidResponse(f"Unexpected response {response!r}.")

    def _get_raw_readings(self) -> Iterator[_Reading]:
        self._send_command(_CMD_GET_READINGS)
        response = list(self._read_text_response())
        if response[0] == b"\x90\x3d":
            logging.debug("No readings available on the meter.")
            return

        for reading in response:
            yield _Reading(*reading.decode("ascii").split(","))

    def get_glucose_unit(self) -> common.Unit:
        for reading in self._get_raw_readings():
            if reading.reading_type != "Glu":
                continue
            return reading.unit
        else:
            logging.debug("No readings in the device, cannot guess glucose unit.")
            return common.Unit.MG_DL

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        for reading in self._get_raw_readings():
            if reading.reading_type != "Glu":
                logging.warning(
                    f"Unsupported reading type {reading.reading_type!r}. Please file an issue at https://github.com/glucometers-tech/glucometerutils/issues"
                )
                continue

            mgdl_value = common.convert_glucose_unit(
                reading.value,
                from_unit=reading.unit,
                to_unit=common.Unit.MG_DL,
            )

            yield common.GlucoseReading(
                reading.timestamp,
                mgdl_value,
                meal=reading.meal,
                comment=reading.comment,
            )
