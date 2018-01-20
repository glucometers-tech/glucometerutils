# -*- coding: utf-8 -*-
"""Driver for Bayer Countour USB
"""

from datetime import datetime

from glucometerutils import common
from glucometerutils.support import hiddevice, lis
from glucometerutils.exceptions import InvalidResponse


class BayerTLVMixin:
    """
    A mixin which should be used in conjunction with the LIS1aMixin
    which implements the lowest layer protocol for the Bayer Contour USB devices
    which is used on top of USB HID messages.
    """
    type_str = b'ABC'

    def _write_lis1a_frame(self, data):
        assert len(data) <= 60

        data = self.type_str + chr(len(data)).encode('ascii') + data
        pad_length = self.blocksize - len(data)
        data += pad_length * b'\x00'

        assert len(data) <= 64

        self._write(data)

    def _read_lis1a_frame(self):
        """
        This seems to be some home-made format.

        it starts with the ASCII string 'ABC', after which follows
        1 byte which contains the length of the data as a normal unsigned
        integer, which should always be <= 60.
        """
        header_size = 4
        data_length_offset = len(self.type_str)

        block = b''
        while True:
            data = self._read()
            if data is None:
                break
            if len(data) <= data_length_offset:
                raise InvalidResponse(data)
            data_length = data[data_length_offset]
            start_byte = header_size
            last_byte = start_byte + data_length
            enc_data = data[start_byte:last_byte]
            block += enc_data

            #
            # Note: when the data is _exactly_ 60 bytes, but
            # is the last bit of data to be read, this won't
            # break the loop, and will read() again, which will
            # block the thread until timeout.
            #
            if len(enc_data) < self.blocksize - header_size:
                break

        return block


class Device(BayerTLVMixin, lis.LIS2a2Mixin, hiddevice.HidDevice):
    blocksize = 64
    USB_VENDOR_ID = 0x1a79
    USB_PRODUCT_ID = 0x6002

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._version_number = 'Unknown'
        self._serial_number = 'Unknown'
        self._glucose_unit = None
        self._readings = []

    def connect(self):
        self.parse_lis2a2_messages()

    def disconnect(self):
        """Disconnect the device, nothing to be done."""
        pass

    def get_version(self):
        return self._version_number

    def get_serial_number(self):
        return self._serial_number

    def get_glucose_unit(self):
        return self._glucose_unit or common.Unit.MMOL_L

    def get_readings(self):
        return self._readings

    def get_meter_info(self):
        return common.MeterInfo(
            'Bayer Contour',
            serial_number=self.get_serial_number(),
            version_info=('Software version: ' + self.get_version(),),
            native_unit=self.get_glucose_unit()
        )

    def get_datetime(self):
        raise NotImplementedError

    def set_datetime(self, date=None):
        raise NotImplementedError

    def zero_log(self):
        raise NotImplementedError

    def _process_lis2a2_header(self, header_fields):
        """
        These are the field types from the LIS2a2 standard for header records.
        They don't exactly match with what I receive from my glucosemeter.
        I'm not sure why that is.

        6.1 Record Type ID
        6.2 Delimiter Definition
        6.3 Message Control ID
        6.4 Access Password
        6.5 Sender Name or ID
        6.6 Sender Street Address
        6.7 Reserved Field
        6.8 Sender Telephone Number
        6.9 Characteristics of Sender
        6.10 Receiver ID
        6.11 Comment or Special Instructions
        6.12 Processing ID
        6.13 Version Number
        6.14 Date and Time of Message
        """
        # My machine returns '2408612' as the serial number, the protocol returns a field
        # containing this: '7390-2408612', this is what i'm settings as the serial number.
        self._serial_number = header_fields.get_component(2, 2, 1)

        # My machine returns 'Versions: DE: 01.26, AE: 01.05, GP 08.02.20' as Versions,
        # but i'm not sure what this means.
        #
        # The protocol returns the following fields, I'm including everything above,
        # plus 'Bayer7390'
        # [['Bayer7390', '01.26'], ['01.05'], ['08.02.20', '7390-2408612', '7397-']]

        self._version_number = '{} DE: {} AE: {} GP: {}'.format(
            header_fields.get_component(2, 0, 0),
            header_fields.get_component(2, 0, 1),
            header_fields.get_component(2, 1, 0),
            header_fields.get_component(2, 2, 0),
        )

    def _process_lis2a2_result(self, result_fields):
        """
        These are the field types from the LIS2a2 standard for result records.
        They don't exactly match with what I receive from my glucosemeter.
        I'm not sure why that is.

        9.1 Record Type ID
        9.2 Sequence Number
        9.3 Universal Test ID
        9.4 Data or Measurement Value
        9.5 LIS2-A2 Units
        9.6 Reference Ranges
        9.7 Result Abnormal Flags
        9.8 Nature of Abnormality Testing
        9.9 Result Status
        9.10 Date of Change in Instrument Normative Values or Units
        9.11 Operator Identification
        9.12 Date/Time Test Started
        9.13 Date/Time Test Completed
        9.14 Instrument Identification
        """

        glucose_unit = result_fields.get_component(4)
        assert glucose_unit in [unit.value for unit in common.Unit], \
            'Expected the glucose unit: {} to be one of {}'.format(glucose_unit, ','.join(common.VALID_UNITS))
        assert self._glucose_unit is None or self._glucose_unit == glucose_unit, \
            'Only results from 1 glucose unit are allowed.'
        self._glucose_unit = glucose_unit

        glucose_level = common.convert_glucose_unit(
            float(result_fields.get_component(3)),
            self.get_glucose_unit(),
            common.Unit.MG_DL
        )
        timestamp = datetime.strptime(result_fields.get_component(8).rstrip('\r'), "%Y%m%d%H%M")

        self._readings.append(common.GlucoseReading(timestamp, glucose_level))
