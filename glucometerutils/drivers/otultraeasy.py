# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2014 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for LifeScan OneTouch Ultra Easy devices.

Also supports OneTouch Ultra Mini devices (different name, same device).

Supported features:
    - get readings;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/ttyUSB0 or similar serial port device.
"""

import binascii
import datetime
import logging
from collections.abc import Generator
from typing import Any, Optional

import construct

from glucometerutils import common, driver
from glucometerutils.support import (
    construct_extras,
    lifescan,
    lifescan_binary_protocol,
    serial,
)

_PACKET = lifescan_binary_protocol.LifeScanPacket(True)

_INVALID_RECORD = 501

_COMMAND_SUCCESS = construct.Const(b"\x05\x06")

_VERSION_REQUEST = construct.Const(b"\x05\x0d\x02")

_VERSION_RESPONSE = construct.Struct(
    success=_COMMAND_SUCCESS,
    version=construct.PascalString(construct.Byte, encoding="ascii"),
)

_SERIAL_NUMBER_REQUEST = construct.Const(
    b"\x05\x0B\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00"
)

_SERIAL_NUMBER_RESPONSE = construct.Struct(
    success=_COMMAND_SUCCESS,
    serial_number=construct.GreedyString(encoding="ascii"),
)

_DATETIME_REQUEST = construct.Struct(
    const=construct.Const(b"\x05\x20"),  # 0x20 is the datetime
    request_type=construct.Enum(construct.Byte, write=0x01, read=0x02),
    timestamp=construct.Default(
        construct_extras.Timestamp(construct.Int32ul),  # type: ignore
        datetime.datetime(1970, 1, 1, 0, 0),
    ),
)

_DATETIME_RESPONSE = construct.Struct(
    success=_COMMAND_SUCCESS,
    timestamp=construct_extras.Timestamp(construct.Int32ul),  # type: ignore
)

_GLUCOSE_UNIT_REQUEST = construct.Const(b"\x05\x09\x02\x09\x00\x00\x00\x00")


_GLUCOSE_UNIT_RESPONSE = construct.Struct(
    success=_COMMAND_SUCCESS,
    unit=lifescan_binary_protocol.GLUCOSE_UNIT,
    padding=construct.Padding(3),
)

_MEMORY_ERASE_REQUEST = construct.Const(b"\x05\x1A")

_READING_COUNT_RESPONSE = construct.Struct(
    const=construct.Const(b"\x0f"),
    count=construct.Int16ul,
)

_READ_RECORD_REQUEST = construct.Struct(
    const=construct.Const(b"\x05\x1f"),
    record_id=construct.Int16ul,
)

_READING_RESPONSE = construct.Struct(
    success=_COMMAND_SUCCESS,
    timestamp=construct_extras.Timestamp(construct.Int32ul),  # type: ignore
    value=construct.Int32ul,
)


def _make_packet(
    message: bytes,
    sequence_number: int,
    expect_receive: bool,
    acknowledge: bool,
    disconnect: bool,
):
    return _PACKET.build(
        {
            "data": {
                "value": {
                    "message": message,
                    "link_control": {
                        "sequence_number": sequence_number,
                        "expect_receive": expect_receive,
                        "acknowledge": acknowledge,
                        "disconnect": disconnect,
                    },
                }
            }
        }
    )


class Device(serial.SerialDevice, driver.GlucometerDevice):
    BAUDRATE = 9600
    DEFAULT_CABLE_ID = "067b:2303"  # Generic PL2303 cable.
    TIMEOUT = 0.5

    def __init__(self, device: Optional[str]) -> None:
        super().__init__(device)

        self.sent_counter_ = False
        self.expect_receive_ = False
        self.buffered_reader_ = construct.Rebuffered(_PACKET, tailcutoff=1024)

    def connect(self) -> None:
        try:
            self._send_packet(b"", disconnect=True)
            self._read_ack()
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def disconnect(self) -> None:
        self.connect()

    def _send_packet(
        self, message: bytes, acknowledge: bool = False, disconnect: bool = False
    ) -> None:
        pkt = _make_packet(
            message, self.sent_counter_, self.expect_receive_, acknowledge, disconnect
        )
        logging.debug("sending packet: %s", binascii.hexlify(pkt))

        self.serial_.write(pkt)
        self.serial_.flush()

    def _read_packet(self) -> construct.Container:
        raw_pkt = self.buffered_reader_.parse_stream(self.serial_).data
        logging.debug("received packet: %r", raw_pkt)

        # discard the checksum and copy
        pkt = raw_pkt.value

        if not pkt.link_control.disconnect and (
            pkt.link_control.sequence_number != self.expect_receive_
        ):
            raise lifescan.MalformedCommand(
                f"at position 2[0b] expected {self.expect_receive_:02x}, received {pkt.link_connect.sequence_count:02x}"
            )

        return pkt

    def _send_ack(self) -> None:
        self._send_packet(b"", acknowledge=True, disconnect=False)

    def _read_ack(self) -> None:
        pkt = self._read_packet()
        assert pkt.link_control.acknowledge

    def _send_request(
        self,
        request_format: construct.Struct,
        request_obj: Optional[dict[str, Any]],
        response_format: construct.Struct,
    ) -> construct.Container:
        try:
            request = request_format.build(request_obj)
            self._send_packet(request, acknowledge=False, disconnect=False)

            self.sent_counter_ = not self.sent_counter_
            self._read_ack()

            response_pkt = self._read_packet()
            assert not response_pkt.link_control.acknowledge

            self.expect_receive_ = not self.expect_receive_
            self._send_ack()

            return response_format.parse(response_pkt.message)
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def get_meter_info(self) -> common.MeterInfo:
        return common.MeterInfo(
            "OneTouch Ultra Easy glucometer",
            serial_number=self.get_serial_number(),
            version_info=("Software version: " + self.get_version(),),
            native_unit=self.get_glucose_unit(),
        )

    def get_version(self) -> str:
        response = self._send_request(_VERSION_REQUEST, None, _VERSION_RESPONSE)

        return response.version

    def get_serial_number(self) -> str:
        response = self._send_request(
            _SERIAL_NUMBER_REQUEST, None, _SERIAL_NUMBER_RESPONSE
        )

        return response.serial_number

    def get_datetime(self) -> datetime.datetime:
        response = self._send_request(
            _DATETIME_REQUEST, {"request_type": "read"}, _DATETIME_RESPONSE
        )

        return response.timestamp

    def _set_device_datetime(self, date: datetime.datetime) -> datetime.datetime:
        response = self._send_request(
            _DATETIME_REQUEST,
            {"request_type": "write", "timestamp": date},
            _DATETIME_RESPONSE,
        )
        return response.timestamp

    def zero_log(self) -> None:
        self._send_request(_MEMORY_ERASE_REQUEST, None, _COMMAND_SUCCESS)

    def get_glucose_unit(self) -> common.Unit:
        response = self._send_request(
            _GLUCOSE_UNIT_REQUEST, None, _GLUCOSE_UNIT_RESPONSE
        )

        return response.unit

    def _get_reading_count(self) -> int:
        response = self._send_request(
            _READ_RECORD_REQUEST,
            {"record_id": _INVALID_RECORD},
            _READING_COUNT_RESPONSE,
        )
        return response.count

    def _get_reading(self, record_id: int) -> common.GlucoseReading:
        response = self._send_request(
            _READ_RECORD_REQUEST, {"record_id": record_id}, _READING_RESPONSE
        )

        return common.GlucoseReading(response.timestamp, float(response.value))

    def get_readings(self) -> Generator[common.AnyReading, None, None]:
        record_count = self._get_reading_count()
        for record_id in range(record_count):
            yield self._get_reading(record_id)
