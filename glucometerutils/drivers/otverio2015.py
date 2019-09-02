# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for LifeScan OneTouch Verio (2015) and Select Plus devices.

Verio 2015 devices can be recognized by microUSB connectors.

Supported features:
    - get readings, including pre-/post-meal notes †;
    - use the glucose unit preset on the device by default;
    - get and set date and time;
    - get serial number and software version;
    - memory reset (caution!)

Expected device path: /dev/sdb or similar USB block device.

† Pre-/post-meal notes are only supported on Select Plus devices.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/lifescan/onetouch-verio-2015

"""

import binascii
import datetime
import logging

import construct
from pyscsi.pyscsi.scsi import SCSI
from pyscsi.pyscsi.scsi_device import SCSIDevice

from glucometerutils import common
from glucometerutils import exceptions
from glucometerutils.support import lifescan
from glucometerutils.support import lifescan_binary_protocol

# This device uses SCSI blocks as registers.
_REGISTER_SIZE = 512

_PACKET = construct.Padded(
    _REGISTER_SIZE,
    lifescan_binary_protocol.LifeScanPacket(False))

_COMMAND_SUCCESS = construct.Const(b'\x03\x06')

_QUERY_REQUEST = construct.Struct(
    construct.Const(b'\x03\xe6\x02'),
    'selector' / construct.Enum(
        construct.Byte, serial=0x00, model=0x01, software=0x02),
)

_QUERY_RESPONSE = construct.Struct(
    construct.Const(b'\x03\x06'),
    'value' / construct.CString(encoding='utf-16-le'),
)

_READ_PARAMETER_REQUEST = construct.Struct(
    construct.Const(b'\x03'),
    'selector' / construct.Enum(
        construct.Byte, unit=0x04),
)

_READ_UNIT_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'unit' / lifescan_binary_protocol.GLUCOSE_UNIT,
    construct.Padding(3),
)

_READ_RTC_REQUEST = construct.Const(b'\x03\x20\x02')

_READ_RTC_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
)

_WRITE_RTC_REQUEST = construct.Struct(
    construct.Const(b'\x03\x20\x01'),
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
)

_MEMORY_ERASE_REQUEST = construct.Const(b'\x03\x1a')

_READ_RECORD_COUNT_REQUEST = construct.Const(b'\x03\x27\x00')

_READ_RECORD_COUNT_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'count' / construct.Int16ul,
)

_READ_RECORD_REQUEST = construct.Struct(
    construct.Const(b'\x03\x31\x02'),
    'record_id' / construct.Int16ul,
    construct.Const(b'\x00'),
)

_MEAL_FLAG = {
    common.Meal.NONE: 0x00,
    common.Meal.BEFORE: 0x01,
    common.Meal.AFTER: 0x02,
}

_READ_RECORD_RESPONSE = construct.Struct(
    _COMMAND_SUCCESS,
    'inverse_counter' / construct.Int16ul,
    construct.Padding(1),
    'lifetime_counter' / construct.Int16ul,
    'timestamp' / lifescan_binary_protocol.VERIO_TIMESTAMP,  # type: ignore
    'value' / construct.Int16ul,
    'meal' / construct.Mapping(
        construct.Byte, _MEAL_FLAG),
    construct.Padding(4),
)

class Device:
    def __init__(self, device):
        if not device:
            raise exceptions.CommandLineError(
                '--device parameter is required, should point to the disk '
                'device representing the meter.')

        self.device_name_ = device
        self.scsi_device_ = SCSIDevice(device, readwrite=True)
        self.scsi_ = SCSI(self.scsi_device_)
        self.scsi_.blocksize = _REGISTER_SIZE

    def connect(self):
        inq = self.scsi_.inquiry()
        logging.debug('Device connected: %r', inq.result)
        vendor = inq.result['t10_vendor_identification'][:32]
        if vendor != b'LifeScan':
            raise exceptions.ConnectionFailed(
                'Device %s is not a LifeScan glucometer.' % self.device_name_)

    def disconnect(self):  # pylint: disable=no-self-use
        return

    def _send_request(self, lba, request_format, request_obj, response_format):
        """Send a request to the meter, and read its response.

        Args:
          lba: (int) the address of the block register to use, known
            valid addresses are 3, 4 and 5.
          request_format: a construct format identifier of the request to send
          request_obj: the object to format with the provided identifier
          response_format: a construct format identifier to parse the returned
            message with.

        Returns:
          The Container object parsed from the response received by the meter.

        Raises:
          lifescan.MalformedCommand if Construct fails to build the request or
            parse the response.

        """
        try:
            request = request_format.build(request_obj)
            request_raw = _PACKET.build({'data': {'value': {
                'message': request,
            }}})
            logging.debug(
                'Request sent: %s', binascii.hexlify(request_raw))
            self.scsi_.write10(lba, 1, request_raw)

            response_raw = self.scsi_.read10(lba, 1)
            logging.debug(
                'Response received: %s', binascii.hexlify(response_raw.datain))
            response_pkt = _PACKET.parse(response_raw.datain).data
            logging.debug('Response packet: %r', response_pkt)

            response = response_format.parse(response_pkt.value.message)
            logging.debug('Response parsed: %r', response)

            return response
        except construct.ConstructError as e:
            raise lifescan.MalformedCommand(str(e))

    def _query_string(self, selector):
        response = self._send_request(
            3, _QUERY_REQUEST, {'selector': selector}, _QUERY_RESPONSE)

        return response.value

    def get_meter_info(self):
        return common.MeterInfo(
            'OneTouch %s glucometer' % self._query_string('model'),
            serial_number=self.get_serial_number(),
            version_info=(
                'Software version: ' + self.get_version(),),
            native_unit=self.get_glucose_unit())

    def get_serial_number(self):
        return self._query_string('serial')

    def get_version(self):
        return self._query_string('software')

    def get_datetime(self):
        response = self._send_request(
            3, _READ_RTC_REQUEST, None, _READ_RTC_RESPONSE)
        return response.timestamp

    def set_datetime(self, date=datetime.datetime.now()):
        self._send_request(
            3, _WRITE_RTC_REQUEST, {'timestamp': date},
            _COMMAND_SUCCESS)

        # The device does not return the new datetime, so confirm by calling
        # READ RTC again.
        return self.get_datetime()

    def zero_log(self):
        self._send_request(
            3, _MEMORY_ERASE_REQUEST, None,
            _COMMAND_SUCCESS)

    def get_glucose_unit(self):
        response = self._send_request(
            4, _READ_PARAMETER_REQUEST, {'selector': 'unit'},
            _READ_UNIT_RESPONSE)
        return response.unit

    def _get_reading_count(self):
        response = self._send_request(
            3, _READ_RECORD_COUNT_REQUEST, None, _READ_RECORD_COUNT_RESPONSE)
        return response.count

    def _get_reading(self, record_id):
        response = self._send_request(
            3, _READ_RECORD_REQUEST, {'record_id': record_id},
            _READ_RECORD_RESPONSE)
        return common.GlucoseReading(
            response.timestamp, float(response.value), meal=response.meal)

    def get_readings(self):
        record_count = self._get_reading_count()
        for record_id in range(record_count):
            yield self._get_reading(record_id)
