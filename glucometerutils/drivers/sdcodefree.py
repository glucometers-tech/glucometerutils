# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2016 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for SD CodeFree devices by SD Biosensor.

For SD Biosensor glucometers using the serial interface.

Supported features:
    - get readings, including pre-/post-meal notes;
    - set date and time.

Expected device path: /dev/ttyUSB0 or similar serial port device.

IMPORTANT NOTE: the glucometer can be connected before starting the program, but
it has to be turned on when the program asks you to.
"""

import binascii
import datetime
import enum
import functools
import logging
import operator
from collections.abc import Generator
from typing import NoReturn

import construct

from glucometerutils import common, driver, exceptions
from glucometerutils.support import serial


def xor_checksum(msg: bytes) -> int:
    return functools.reduce(operator.xor, msg)


class Direction(enum.Enum):
    In = 0x20
    Out = 0x10


_PACKET = construct.Struct(
    stx=construct.Const(0x53, construct.Byte),
    direction=construct.Mapping(construct.Byte, {e: e.value for e in Direction}),
    length=construct.Rebuild(construct.Byte, lambda this: len(this.message) + 2),
    message=construct.Bytes(lambda this: this.length - 2),
    checksum=construct.Checksum(construct.Byte, xor_checksum, construct.this.message),
    etx=construct.Const(0xAA, construct.Byte),
)

_FIRST_MESSAGE = construct.Struct(
    const_1=construct.Const(0x30, construct.Byte),
    count=construct.Int16ub,
    const_2=construct.Const(0xAA, construct.Byte)[19],
)

_CHALLENGE_PACKET_FULL = b"\x53\x20\x04\x10\x30\x20\xAA"
_RESPONSE_MESSAGE = b"\x10\x40"

_DATE_SET_MESSAGE = b"\x10\x10"

_DISCONNECT_MESSAGE = b"\x10\x60"
_DISCONNECTED_MESSAGE = b"\x10\x70"

_FETCH_MESSAGE = b"\x10\x60"

_MEAL_FLAG = {
    common.Meal.NONE: 0x00,
    common.Meal.BEFORE: 0x10,
    common.Meal.AFTER: 0x20,
}

_READING = construct.Struct(
    unknown_1=construct.Byte[2],
    year=construct.Byte,
    month=construct.Byte,
    day=construct.Byte,
    hour=construct.Byte,
    minute=construct.Byte,
    value=construct.Int16ub,
    meal=construct.Mapping(construct.Byte, _MEAL_FLAG),
    unknown_2=construct.Byte[7],
)


class Device(serial.SerialDevice, driver.GlucometerDevice):
    BAUDRATE = 38400
    DEFAULT_CABLE_ID = "10c4:ea60"  # Generic cable.
    TIMEOUT = 300  # We need to wait for data from the device.

    def read_message(self) -> bytes:
        pkt = _PACKET.parse_stream(self.serial_)
        logging.debug("received packet: %r", pkt)
        return pkt.message

    def wait_and_ready(self) -> int:
        challenge = b"\0"
        while challenge == b"\0":
            challenge = self.serial_.read(1)

            # The first packet read may have a prefixed zero, it might be a bug
            # in the cp210x driver or device, but discard it if found.
            if challenge == b"\0":
                logging.debug("spurious null byte received")
                continue
            if challenge != b"\x53":
                raise exceptions.ConnectionFailed(
                    message=f"Unexpected starting bytes {challenge!r}"
                )

        challenge += self.serial_.read(6)

        if challenge != _CHALLENGE_PACKET_FULL:
            raise exceptions.ConnectionFailed(
                message=f"Unexpected challenge {challenge!r}"
            )

        logging.debug("challenge packet received: %s", binascii.hexlify(challenge))

        self.send_message(_RESPONSE_MESSAGE)

        # The first packet only contains the counter of how many readings are
        # available.
        first_message = _FIRST_MESSAGE.parse(self.read_message())
        logging.debug("received first message: %r", first_message)

        return first_message.count

    def send_message(self, message: bytes) -> None:
        pkt = _PACKET.build({"message": message, "direction": Direction.Out})
        logging.debug("sending packet: %s", binascii.hexlify(pkt))
        self.serial_.write(pkt)

    def connect(self) -> None:  # pylint: disable=no-self-use
        print("Please connect and turn on the device.")

    def disconnect(self) -> None:
        self.send_message(_DISCONNECT_MESSAGE)
        response = self.read_message()
        if response != _DISCONNECTED_MESSAGE:
            raise exceptions.InvalidResponse(response=repr(response))

    def get_meter_info(self) -> common.MeterInfo:  # pylint: disable=no-self-use
        return common.MeterInfo("SD CodeFree glucometer")

    def get_version(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def get_serial_number(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def get_glucose_unit(self) -> common.Unit:  # pylint: disable=no-self-use
        # Device does not provide information on glucose unit.
        return common.Unit.MG_DL

    def get_datetime(self) -> NoReturn:  # pylint: disable=no-self-use
        raise NotImplementedError

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        setdatecmd = date.strftime("ADATE%Y%m%d%H%M").encode("ascii")

        # Ignore the readings count.
        self.wait_and_ready()

        self.send_message(setdatecmd)
        response = self.read_message()
        if response != _DATE_SET_MESSAGE:
            raise exceptions.InvalidResponse(response=repr(response))

        # The date we return should only include up to minute, unfortunately.
        return datetime.datetime(
            date.year, date.month, date.day, date.hour, date.minute
        )

    def zero_log(self) -> NoReturn:
        raise NotImplementedError

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        count = self.wait_and_ready()

        for _ in range(count):
            self.send_message(_FETCH_MESSAGE)
            message = self.read_message()

            reading = _READING.parse(message)
            logging.debug("received reading: %r", reading)

            yield common.GlucoseReading(
                datetime.datetime(
                    2000 + reading.year,
                    reading.month,
                    reading.day,
                    reading.hour,
                    reading.minute,
                ),
                reading.value,
                meal=reading.meal,
            )
