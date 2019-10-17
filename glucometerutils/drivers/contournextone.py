# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MIT
"""Driver for ContourUSB devices.

Supported features:
    - get readings (blood glucose), including comments;
    - get date and time;
    - get serial number and software version;
    - get device info (e.g. unit)

Expected device path: /dev/hidraw4 or similar HID device. Optional when using
HIDAPI.

Further information on the device protocol can be found at

http://protocols.ascensia.com/Programming-Guide.aspx

"""

import datetime

from glucometerutils import common
from glucometerutils.support import contour

import re



class FrameError(Exception):
    pass


class Device(contour.ContourHidDevice):
    """Glucometer driver for Contour Next One devices."""

    # regexr.com/4k6jb
    _HEADER_RECORD_RE = re.compile(
        "^(?P<record_type>[a-zA-Z])\\|(?P<field_del>.)(?P<repeat_del>.)"
        "(?P<component_del>.)(?P<escape_del>.)\\|\\w*\\"
        "|(?P<product_code>\\w+)\\^(?P<dig_ver>[0-9]{2}\\.[0-9]{2})"
        "\\\\(?P<alg_ver>[0-9]{2}\\.[0-9]{2})\\\\"
        "(?P<rfe_ver>[0-9]{2}\\.[0-9]{2})\\^(?P<serial_num>[0-9]{4}\\"
        "-[0-9]{7})\\|A=(?P<res_marking>[0-9])\\"
        "^C=(?P<config_bits>[0-9])\\^R=(?P<ref_method>[0-9])\\"
        "^S=(?P<reserved>[0-9])\\^U=(?P<unit>[0-9])\\"
        "^V=(?P<lo_bound>[0-9]{2})(?P<hi_bound>[0-9]{3})\\"
        "^X=(?P<post_lo>[0-9]{3})(?P<fasting_lo>[0-9]{3})"
        "(?P<post_hi>[0-9]{3})(?P<fasting_hi>[0-9]{3})\\"
        "^a=(?P<target_ind>[0-9]{1})\\"
        "^J=(?P<sensor_type>[0-9]{1})\\|(?P<total>[0-9]{1})"
        "\\|\\|\\|\\|\\|P\\|1\\|(?P<datetime>[0-9]+)\\|"
    )

    _RESULT_RECORD_RE = re.compile(
        "^(?P<record_type>[a-zA-Z])\\|(?P<seq_num>[0-9]+)\\|"
        "\\w*\\^\\w*\\^\\w*\\^(?P<test_id>\\w+)\\|(?P<value>[0-9]+)\\"
        "|(?P<unit>\\w+\\/\\w+)\\^(?P<ref_method>[BPD])\\|\\"
        "|(?P<markers>[T0-9\\/M<>BAFcbCZAB]*)\\|\\|"
        "(?P<datetime>[0-9]+)")

    _RECORD_FORMAT = re.compile(
        '\x02(?P<check>(?P<recno>[0-7])(?P<text>[^\x0d]*)'
        '\x0d(?P<end>[\x03\x17]))'
        '(?P<checksum>[0-9A-F][0-9A-F])\x0d\x0a')

    _MESSAGE_TERMINATOR_RECORD_RE = re.compile(
        "^L\\|1\\|\\w*\\|N")

    USB_VENDOR_ID = 0x1a79  # type: int  # Bayer Health Care LLC Contour
    USB_PRODUCT_ID = 0x6002  # type: int

    ACK = '\x06'
    CAN = '\x18'
    CR = '\x0d'
    ENQ = '\x05'
    EOT = '\x04'
    ETB = '\x17'
    ETX = '\x03'
    LF = '\x0A'
    NAK = '\x15'
    STX = '\x02'

    def extract_timestamp(self,parsed_record, prefix=''):
        """Extract the timestamp from a parsed record.

        This leverages the fact that all the reading records have the same base structure.
        """
        datetime_str = parsed_record['datetime']

        return datetime.datetime(
            int(datetime_str[0:4]),  # year
            int(datetime_str[4:6]),  # month
            int(datetime_str[6:8]),  # day
            int(datetime_str[8:10]),  # hours
            int(datetime_str[10:12]),  # minutes
            int(datetime_str[12:14])   #seconds
            )


    def parse_header_record(self, text):
        header = self._HEADER_RECORD_RE.search(text)

        self.field_del = header.group('field_del')
        self.repeat_del = header.group('repeat_del')
        self.component_del = header.group('component_del')
        self.escape_del = header.group('escape_del')

        self.product_code = header.group('product_code')
        self.dig_ver = header.group('dig_ver')
        self.alg_ver = header.group('alg_ver')
        self.rfe_ver = header.group('rfe_ver')

        self.serial_num = header.group('serial_num')
        self.res_marking = header.group('res_marking')
        self.config_bits = header.group('config_bits')
        self.ref_method = header.group('ref_method')

        # U limit
        self.unit = header.group('unit')
        self.lo_bound = header.group('lo_bound')
        self.hi_bound = header.group('hi_bound')

        # X field
        self.post_lo = header.group('post_lo')
        self.fasting_lo = header.group('fasting_lo')
        self.post_hi = header.group('post_hi')
        self.fasting_hi = header.group('fasting_hi')

        self.target_ind = header.group("target_ind")
        self.sensor_type = header.group("sensor_type")
        self.total = header.group('total')
        # Datetime string in YYYYMMDDHHMM format
        self.datetime = header.group('datetime')

    def sync(self):
        """
        Sync with meter and yield received data frames
        FSM implemented by Anders Hammarquist's for glucodump
        More info: https://bitbucket.org/iko/glucodump/src/default/
        """
        self.state = self.mode_establish
        try:
            tometer = self.ACK
            result = None
            foo = 0
            while True:
                self.write(tometer)
                if result is not None and self.state == self.mode_data:
                    yield result
                result = None
                data_bytes = self.read()
                data = data_bytes.decode()
                stx = data.find(self.STX)
                if stx != -1:
                    # got <STX>, parse frame
                    try:
                        result = self.checkframe(data[stx:])
                        if self._MESSAGE_TERMINATOR_RECORD_RE.match(result):
                            self.write(self.ACK)
                            break
                        tometer = self.ACK
                        self.state = self.mode_data
                    except FrameError as e:
                        tometer = self.NAK  # Couldn't parse, <NAK>
                else:
                    # Got something we don't understand, <NAK> it
                    tometer = self.NAK
        except Exception as e:
            raise e

    def get_meter_info(self):
        """Return the device information in structured form."""
        self._get_info_record()
        return common.MeterInfo(
            'Contour Next One',
            serial_number=self._get_serial_number(),
            version_info=(
                'Meter versions: ' + self.get_version(),),
            native_unit=self.get_glucose_unit())

    def get_glucose_unit(self):  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""

        if self._get_glucose_unit() == '0':
            return common.Unit.MG_DL
        else:
            return common.Unit.MMOL_L

    def get_version(self):
        # type: () -> Text
        """Return the software version of the device."""
        return self.dig_ver + " - " + self.alg_ver + " - " + self.rfe_ver

    def get_readings(self):
        """
        Get reading dump from download data mode(all readings stored)
        This meter supports only blood samples
        """
        for parsed_record in self._get_multirecord():
            yield common.GlucoseReading(
                self.extract_timestamp(parsed_record),
                int(parsed_record['value']),
                comment=parsed_record['markers'],
                measure_method=common.MeasurementMethod.BLOOD_SAMPLE
            )
