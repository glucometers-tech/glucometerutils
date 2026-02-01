# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2026 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Support code for Accu-Chek Guide and compatible USB devices."""

from __future__ import annotations

import datetime
import logging
from collections.abc import Generator
from typing import Optional

import usb.core
import usb.util

from glucometerutils import common, exceptions

_SUPPORTED_USB_IDS = (
    (0x173A, 0x21D5),  # Roche Accu-Chek Guide
    (0x173A, 0x21D7),  # Similar Roche device
    (0x173A, 0x21D8),  # Roche Relion Platinum
)

# APDU and protocol constants
kAPDU_TYPE_ASSOCIATION_REQUEST = 0xE200
kAPDU_TYPE_ASSOCIATION_RESPONSE = 0xE300
kAPDU_TYPE_ASSOCIATION_RELEASE_REQUEST = 0xE400
kAPDU_TYPE_ASSOCIATION_RELEASE_RESPONSE = 0xE500
kAPDU_TYPE_ASSOCIATION_ABORT = 0xE600
kAPDU_TYPE_PRESENTATION_APDU = 0xE700

kDATA_ADPU_INVOKE_GET = 0x0103
kDATA_ADPU_INVOKE_CONFIRMED_ACTION = 0x0107
kDATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT = 0x0201

kEVENT_TYPE_MDC_NOTI_CONFIG = 0x0D1C
kEVENT_TYPE_MDC_NOTI_SEGMENT_DATA = 0x0D21

kACTION_TYPE_MDC_ACT_SEG_GET_INFO = 0x0C0D
kACTION_TYPE_MDC_ACT_SEG_TRIG_XFER = 0x0C1C

kMDC_MOC_VMO_PMSTORE = 61
kMDC_ATTR_NUM_SEG = 2385

_DEFAULT_TIMEOUT_MS = 5000
_DEFAULT_BUFFER_SIZE = 1024


def _bcd_to_int(value: int) -> int:
    return ((value >> 4) * 10) + (value & 0x0F)


def _read_u16(buffer: bytes, offset: int) -> tuple[int, int]:
    if offset + 2 > len(buffer):
        raise exceptions.InvalidResponse("Buffer underrun")
    return int.from_bytes(buffer[offset : offset + 2], "big"), offset + 2


def _read_u32(buffer: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(buffer):
        raise exceptions.InvalidResponse("Buffer underrun")
    return int.from_bytes(buffer[offset : offset + 4], "big"), offset + 4


def _be16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _be32(value: int) -> bytes:
    return value.to_bytes(4, "big")


def _parse_vid_pid(device: str) -> tuple[int, int]:
    parts = device.split(":")
    if len(parts) != 2:
        raise exceptions.CommandLineError(
            "--device must be in vid:pid format (hex or decimal)."
        )

    def _parse_part(part: str) -> int:
        base = (
            16
            if any(c in part.lower() for c in "abcdef") or part.startswith("0x")
            else 10
        )
        return int(part, base)

    return _parse_part(parts[0]), _parse_part(parts[1])


def _find_matching_device(device: Optional[str]) -> usb.core.Device:
    if device:
        vendor_id, product_id = _parse_vid_pid(device)
        dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if dev is None:
            raise exceptions.ConnectionFailed(
                f"Device {vendor_id:04x}:{product_id:04x} not found."
            )
        return dev

    for vendor_id, product_id in _SUPPORTED_USB_IDS:
        dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
        if dev is not None:
            return dev

    raise exceptions.ConnectionFailed("No supported Accu-Chek USB device found.")


def _select_interface_and_endpoints(
    dev: usb.core.Device,
) -> tuple[usb.core.Interface, usb.core.Endpoint, usb.core.Endpoint]:
    cfg = dev.get_active_configuration()
    for interface in cfg:
        if interface.bNumEndpoints != 2:
            continue

        ep_in = None
        ep_out = None
        for endpoint in interface:
            if endpoint.wMaxPacketSize != 64:
                continue
            if (
                usb.util.endpoint_type(endpoint.bmAttributes)
                != usb.util.ENDPOINT_TYPE_BULK
            ):
                continue
            direction = usb.util.endpoint_direction(endpoint.bEndpointAddress)
            if direction == usb.util.ENDPOINT_IN:
                ep_in = endpoint
            else:
                ep_out = endpoint

        if ep_in and ep_out:
            return interface, ep_in, ep_out

    raise exceptions.ConnectionFailed(
        "Device does not match expected Accu-Chek USB interface layout."
    )


class AccuChekGuideSession:
    def __init__(self, device: Optional[str]) -> None:
        self._device_selector = device
        self._device: Optional[usb.core.Device] = None
        self._interface: Optional[usb.core.Interface] = None
        self._ep_in: Optional[usb.core.Endpoint] = None
        self._ep_out: Optional[usb.core.Endpoint] = None
        self._needs_reattach = False
        self._invoke_id: Optional[int] = None
        self._pm_store_handle: Optional[int] = None
        self._manufacturer: Optional[str] = None
        self._product: Optional[str] = None
        self._serial: Optional[str] = None

    def open(self) -> None:
        if self._device:
            return

        dev = _find_matching_device(self._device_selector)
        try:
            dev.set_configuration()
        except usb.core.USBError:
            # Configuration may already be set, ignore.
            pass

        interface, ep_in, ep_out = _select_interface_and_endpoints(dev)

        try:
            if dev.is_kernel_driver_active(interface.bInterfaceNumber):
                dev.detach_kernel_driver(interface.bInterfaceNumber)
                self._needs_reattach = True
        except (NotImplementedError, usb.core.USBError):
            self._needs_reattach = False

        usb.util.claim_interface(dev, interface.bInterfaceNumber)
        try:
            dev.set_interface_altsetting(
                interface=interface.bInterfaceNumber,
                alternate_setting=interface.bAlternateSetting,
            )
        except usb.core.USBError:
            # Some devices may not support alternate settings.
            pass

        self._device = dev
        self._interface = interface
        self._ep_in = ep_in
        self._ep_out = ep_out

        try:
            if dev.iManufacturer:
                self._manufacturer = usb.util.get_string(dev, dev.iManufacturer)
            if dev.iProduct:
                self._product = usb.util.get_string(dev, dev.iProduct)
            if dev.iSerialNumber:
                self._serial = usb.util.get_string(dev, dev.iSerialNumber)
        except usb.core.USBError:
            pass

        logging.info(
            "Connected Accu-Chek USB device %04x:%04x on bus %s address %s",
            dev.idVendor,
            dev.idProduct,
            getattr(dev, "bus", "?"),
            getattr(dev, "address", "?"),
        )

    def close(self) -> None:
        if not self._device or not self._interface:
            return

        try:
            usb.util.release_interface(self._device, self._interface.bInterfaceNumber)
        except usb.core.USBError:
            pass

        if self._needs_reattach:
            try:
                self._device.attach_kernel_driver(self._interface.bInterfaceNumber)
            except usb.core.USBError:
                pass

        usb.util.dispose_resources(self._device)
        self._device = None
        self._interface = None
        self._ep_in = None
        self._ep_out = None
        self._invoke_id = None
        self._pm_store_handle = None

    def get_model_name(self) -> str:
        if self._manufacturer and self._product:
            return f"{self._manufacturer} {self._product}".strip()
        if self._product:
            return self._product
        return "Accu-Chek USB"

    def get_serial_number(self) -> str:
        return self._serial or "N/A"

    def _bulk_write(self, payload: bytes) -> None:
        assert self._ep_out is not None
        try:
            written = self._ep_out.write(payload, timeout=_DEFAULT_TIMEOUT_MS)
        except usb.core.USBError as exc:
            raise exceptions.CommandError(f"USB write failed: {exc}") from exc
        if written != len(payload):
            raise exceptions.CommandError(
                f"USB short write: {written} of {len(payload)} bytes."
            )

    def _bulk_read(self, size: int = _DEFAULT_BUFFER_SIZE) -> bytes:
        assert self._ep_in is not None
        try:
            data = self._ep_in.read(size, timeout=_DEFAULT_TIMEOUT_MS)
        except usb.core.USBError as exc:
            raise exceptions.CommandError(f"USB read failed: {exc}") from exc
        return bytes(data)

    def _control_get_status(self) -> None:
        assert self._device is not None
        try:
            self._device.ctrl_transfer(
                0x80,  # standard, device, IN
                0x00,  # GET_STATUS
                0,
                0,
                2,
                timeout=_DEFAULT_TIMEOUT_MS,
            )
        except usb.core.USBError as exc:
            raise exceptions.CommandError(
                f"USB control transfer failed: {exc}"
            ) from exc

    def _set_invoke_id(self, buffer: bytes, offset: int = 6) -> None:
        invoke_id, _ = _read_u16(buffer, offset)
        self._invoke_id = invoke_id

    def _next_invoke_id(self) -> int:
        assert self._invoke_id is not None
        return (self._invoke_id + 1) & 0xFFFF

    def _build_pairing_confirmation(self) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_ASSOCIATION_RESPONSE),
                _be16(44),
                _be16(0x0003),
                _be16(20601),
                _be16(38),
                _be32(0x80000002),
                _be16(0x8000),
                _be32(0x80000000),
                _be32(0),
                _be32(0x80000000),
                _be16(8),
                _be32(0x12345678),
                _be32(0),
                _be32(0),
                _be32(0),
                _be16(0),
            ]
        )

    def _build_config_confirm(self, invoke_id: int) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_PRESENTATION_APDU),
                _be16(22),
                _be16(20),
                _be16(invoke_id),
                _be16(kDATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT),
                _be16(14),
                _be16(0),
                _be32(0),
                _be16(kEVENT_TYPE_MDC_NOTI_CONFIG),
                _be16(4),
                _be16(0x4000),
                _be16(0),
            ]
        )

    def _build_mds_attribute_request(self, invoke_id: int) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_PRESENTATION_APDU),
                _be16(14),
                _be16(12),
                _be16(invoke_id),
                _be16(kDATA_ADPU_INVOKE_GET),
                _be16(6),
                _be16(0),
                _be32(0),
            ]
        )

    def _build_action_request(self, invoke_id: int, pm_store_handle: int) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_PRESENTATION_APDU),
                _be16(20),
                _be16(18),
                _be16(invoke_id),
                _be16(kDATA_ADPU_INVOKE_CONFIRMED_ACTION),
                _be16(12),
                _be16(pm_store_handle),
                _be16(kACTION_TYPE_MDC_ACT_SEG_GET_INFO),
                _be16(6),
                _be16(1),
                _be16(2),
                _be16(0),
            ]
        )

    def _build_request_segments(self, invoke_id: int, pm_store_handle: int) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_PRESENTATION_APDU),
                _be16(16),
                _be16(14),
                _be16(invoke_id),
                _be16(kDATA_ADPU_INVOKE_CONFIRMED_ACTION),
                _be16(8),
                _be16(pm_store_handle),
                _be16(kACTION_TYPE_MDC_ACT_SEG_TRIG_XFER),
                _be16(2),
                _be16(0),
            ]
        )

    def _build_segment_ack(
        self, invoke_id: int, pm_store_handle: int, u0: int, u1: int, u2: int
    ) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_PRESENTATION_APDU),
                _be16(30),
                _be16(28),
                _be16(invoke_id),
                _be16(kDATA_ADPU_RESPONSE_CONFIRMED_EVENT_REPORT),
                _be16(22),
                _be16(pm_store_handle),
                _be32(0xFFFFFFFF),
                _be16(kEVENT_TYPE_MDC_NOTI_SEGMENT_DATA),
                _be16(12),
                _be32(u0),
                _be32(u1),
                _be16(u2),
                _be16(0x0080),
            ]
        )

    def _build_release_request(self) -> bytes:
        return b"".join(
            [
                _be16(kAPDU_TYPE_ASSOCIATION_RELEASE_REQUEST),
                _be16(2),
                _be16(0),
            ]
        )

    def _parse_config_info(self, buffer: bytes) -> int:
        offset = 24
        obj_count, offset = _read_u16(buffer, offset)
        _, offset = _read_u16(buffer, offset)

        pm_store_handle = None
        pm_store_attr_count = None
        pm_store_offset = None

        for _ in range(obj_count):
            obj_class, offset = _read_u16(buffer, offset)
            obj_handle, offset = _read_u16(buffer, offset)
            obj_attr_count, offset = _read_u16(buffer, offset)
            obj_size, offset = _read_u16(buffer, offset)
            if obj_class == kMDC_MOC_VMO_PMSTORE:
                pm_store_handle = obj_handle
                pm_store_attr_count = obj_attr_count
                pm_store_offset = offset
            offset += obj_size

        if (
            pm_store_handle is None
            or pm_store_attr_count is None
            or pm_store_offset is None
        ):
            raise exceptions.InvalidResponse(
                "PM store object not found in config info."
            )

        attr_offset = pm_store_offset
        for _ in range(pm_store_attr_count):
            attr_class, attr_offset = _read_u16(buffer, attr_offset)
            attr_size, attr_offset = _read_u16(buffer, attr_offset)
            if attr_class == kMDC_ATTR_NUM_SEG:
                if attr_offset + attr_size > len(buffer):
                    raise exceptions.InvalidResponse("Attribute data truncated.")
                num_segments = int.from_bytes(
                    buffer[attr_offset : attr_offset + 2], "big"
                )
                logging.info("Accu-Chek reports %d segments", num_segments)
                return pm_store_handle
            attr_offset += attr_size

        raise exceptions.InvalidResponse("Segment count attribute not found.")

    def _prepare_transfer(self) -> None:
        self._control_get_status()
        self._bulk_read(64)  # pairing request
        self._bulk_write(self._build_pairing_confirmation())

        config_info = self._bulk_read(_DEFAULT_BUFFER_SIZE)
        self._set_invoke_id(config_info)
        self._pm_store_handle = self._parse_config_info(config_info)
        if self._pm_store_handle is None:
            raise exceptions.InvalidResponse("Missing PM store handle.")

        self._bulk_write(self._build_config_confirm(self._invoke_id or 0))

        self._bulk_write(self._build_mds_attribute_request(self._next_invoke_id()))
        mds_answer = self._bulk_read(_DEFAULT_BUFFER_SIZE)
        ret_code, _ = _read_u16(mds_answer, 0)
        if ret_code == kAPDU_TYPE_ASSOCIATION_ABORT:
            raise exceptions.ConnectionFailed(
                "Device aborted association while reading MDS attributes."
            )
        self._set_invoke_id(mds_answer)

        self._bulk_write(
            self._build_action_request(self._next_invoke_id(), self._pm_store_handle)
        )
        action_answer = self._bulk_read(_DEFAULT_BUFFER_SIZE)
        self._set_invoke_id(action_answer)

        self._bulk_write(
            self._build_request_segments(self._next_invoke_id(), self._pm_store_handle)
        )
        segment_headers = self._bulk_read(_DEFAULT_BUFFER_SIZE)
        self._set_invoke_id(segment_headers)

        if len(segment_headers) == 22:
            response_code = int.from_bytes(segment_headers[20:22], "big")
            if response_code != 0:
                raise exceptions.ConnectionFailed(
                    f"Device returned error code {response_code} when requesting segments."
                )

        if len(segment_headers) < 22:
            raise exceptions.InvalidResponse("Segment header response too short.")

        header_value = int.from_bytes(segment_headers[14:16], "big")
        if header_value != kACTION_TYPE_MDC_ACT_SEG_TRIG_XFER:
            raise exceptions.InvalidResponse("Unexpected segment header response.")

    def _release(self) -> None:
        try:
            self._bulk_write(self._build_release_request())
            self._bulk_read(_DEFAULT_BUFFER_SIZE)
        except exceptions.Error:
            # Ignore errors on release.
            pass

    def iter_readings(self) -> Generator[common.AnyReading, None, None]:
        assert self._pm_store_handle is not None

        while True:
            data_segment = self._bulk_read(_DEFAULT_BUFFER_SIZE)
            if len(data_segment) < 40:
                raise exceptions.InvalidResponse("Data segment too short.")

            status = data_segment[32]
            self._set_invoke_id(data_segment)

            offset = 22
            u0, offset = _read_u32(data_segment, offset)
            u1, offset = _read_u32(data_segment, offset)
            u2, offset = _read_u16(data_segment, offset)

            entry_offset = 30
            nb_entries, entry_offset = _read_u16(data_segment, entry_offset)
            entry_offset -= 2

            for _ in range(nb_entries):
                cc = _bcd_to_int(data_segment[6 + entry_offset])
                yy = _bcd_to_int(data_segment[7 + entry_offset])
                mm = _bcd_to_int(data_segment[8 + entry_offset])
                dd = _bcd_to_int(data_segment[9 + entry_offset])
                hh = _bcd_to_int(data_segment[10 + entry_offset])
                mn = _bcd_to_int(data_segment[11 + entry_offset])

                reading_offset = 14 + entry_offset
                value = int.from_bytes(
                    data_segment[reading_offset : reading_offset + 2], "big"
                )
                status_code = int.from_bytes(
                    data_segment[reading_offset + 2 : reading_offset + 4], "big"
                )
                entry_offset += 12

                if status_code != 0:
                    continue

                year = (cc * 100) + yy
                try:
                    timestamp = datetime.datetime(year, mm, dd, hh, mn)
                except ValueError as exc:
                    raise exceptions.InvalidDateTime() from exc

                yield common.GlucoseReading(timestamp, float(value))

            self._bulk_write(
                self._build_segment_ack(
                    self._invoke_id or 0, self._pm_store_handle, u0, u1, u2
                )
            )

            if status & 0x40:
                break

    def download_readings(self) -> Generator[common.AnyReading, None, None]:
        self._prepare_transfer()
        try:
            yield from self.iter_readings()
        finally:
            self._release()
