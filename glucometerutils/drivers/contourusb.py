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


def _extract_timestamp(parsed_record, prefix=''):
    """Extract the timestamp from a parsed record.

    This leverages the fact that all the reading records have the same base structure.
    """
    datetime_str = parsed_record['datetime']

    return datetime.datetime(
        int(datetime_str[0:4]),  # year
        int(datetime_str[4:6]),  # month
        int(datetime_str[6:8]),  # day
        int(datetime_str[8:10]),  # hour
        int(datetime_str[10:12]),  # minute
        0)


class Device(contour.ContourHidDevice):
    """Glucometer driver for FreeStyle Libre devices."""

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

    def parse_header_record(self, text):
        header = self._HEADER_RECORD_RE.search(text)

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

    def get_meter_info(self):
        """Return the device information in structured form."""
        self._get_info_record()
        return common.MeterInfo(
            'Contour USB',
            serial_number=self._get_serial_number(),
            version_info=(
                'Meter versions: ' + self._get_version(),),
            native_unit=self.get_glucose_unit())

    def get_glucose_unit(self):  # pylint: disable=no-self-use
        """Returns the glucose unit of the device."""

        if self._get_glucose_unit() == '0':
            return common.Unit.MG_DL
        else:
            return common.Unit.MMOL_L

    def _get_version(self):
        # type: () -> Text
        """Return the software version of the device."""
        return self.dig_ver + " - " + self.anlg_ver + " - " + self.agp_ver

    def get_readings(self):
        """
        Get reading dump from download data mode(all readings stored)
        This meter supports only blood samples
        """
        for parsed_record in self._get_multirecord():
            yield common.GlucoseReading(
                _extract_timestamp(parsed_record),
                int(parsed_record['value']),
                comment=parsed_record['markers'],
                measure_method=common.MeasurementMethod.BLOOD_SAMPLE
            )
