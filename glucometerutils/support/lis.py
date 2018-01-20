from glucometerutils.exceptions import InvalidResponse, InvalidChecksum

ASCII_STX = b'\x02'
ASCII_ETX = b'\x03'
ASCII_EOT = b'\x04'
ASCII_ENQ = b'\x05'
ASCII_ACK = b'\x06'
ASCII_ETB = b'\x17'
ASCII_LF = b'\n'
ASCII_CR = b'\r'


class Fields:
    def __init__(self, fields):
        """
        :param fields: a list of fields, a field is another list of repeat
                       records, and a repeat record is another list of
                       components.
        """
        self.fields = fields

    @classmethod
    def from_string(cls, delimiters, data):
        """
        :param delimiters: a dictionary with keys: 'component', 'repeat' and 'field' with
                           as values the LIS2-a2 delimiter characters.
        :param data:
        """
        fields = [[[component
                    for component in repeat.split(delimiters['component'])]
                   for repeat in field.split(delimiters['repeat'])]
                  for field in data.split(delimiters['field'])]

        return cls(fields)

    def get_component(self, field, repeat=0, component=0):
        try:
            return self.fields[field][repeat][component].decode('latin1')
        except IndexError:
            raise InvalidResponse('Could not find field: {} repeat: {} component: {} in {}'.format(field, repeat, component, str(self.fields)))


class LIS1aMixin:
    def _write_lis1a_frame(self, data):
        """
        Write the LIS1a frame to the lower level protocol.
        """
        raise NotImplementedError

    def _read_lis1a_frame(self):
        """
        Read the LIS1a frame from the lower level protocol. 
        """
        raise NotImplementedError

    def _parse_lis1a_transfer_frame(self, previous_frame_number, data):
        """
        6.3 Process the LIS1A transfer frame.

        <STX> FN text <ETB> C1 C2 <CR> <LF> (intermediate frame)
        <STX> FN text <ETX> C1 C2 <CR> <LF> (end frame)
        """

        if data[:1] != ASCII_STX:
            raise InvalidResponse(data)

        try:
            frame_number = int(data[1:2])
        except ValueError:
            raise InvalidResponse(data)

        if frame_number > 7:
            raise InvalidResponse(data)

        if frame_number != (previous_frame_number + 1) % 8:
            raise InvalidResponse(data)

        if data[-5:-4] not in [ASCII_ETX, ASCII_ETB]:
            raise InvalidResponse(data)
        is_end_frame = data[-5:-4] == ASCII_ETX

        # 6.3.3 - Checksum
        try:
            checksum = int(data[-4:-2], 16)
        except ValueError:
            raise InvalidResponse(data)
        calculated_checksum = sum([c for c in data[1:-4]]) % 256
        if calculated_checksum != checksum:
            raise InvalidChecksum(calculated_checksum, checksum)

        if data[-2:] != ASCII_CR + ASCII_LF:
            raise InvalidResponse(data)

        text = data[2:-5]

        return frame_number, is_end_frame, text

    def _parse_lis1a_transfer_frames(self, data):
        previous_frame_number = 0
        frames = []
        while True:
            data = self._read_lis1a_frame()
            frame_number, is_end_frame, text = self._parse_lis1a_transfer_frame(previous_frame_number, data)
            previous_frame_number = frame_number
            frames.append(text)

            # LIS1-A 6.3.4.2
            self._write_lis1a_frame(ASCII_ACK)

            if is_end_frame:
                break

        return frames


class LIS2a2Mixin(LIS1aMixin):
    def _parse_delimiters(self, data):
        delimiters = data[1:5]
        if len(delimiters) != 4:
            raise InvalidResponse(data)
        delimiters = {
            'field': data[1:2],
            'repeat': data[2:3],
            'component': data[3:4],
            'escape': data[4:5],
        }
        # Either this is the end of the record (no field delimiter needed)
        # or is the end of the field.
        if data[6:7] not in ['', delimiters['field']]:
            raise InvalidResponse(data)
        return delimiters

    def _process_lis2a2_header(header_fields):
        raise NotImplementedError

    def _process_lis2a2_result(result_fields):
        raise NotImplementedError

    def _parse_lis2a2_message(self, frames):
        # From the header record, the delimiters are determined.
        header_frame = next(frames)
        delimiters = self._parse_delimiters(header_frame)
        header_fields = Fields.from_string(delimiters, header_frame[6:])

        self._process_lis2a2_header(header_fields)

        # TODO: Only support for 1 patient frame.
        try:
            patient_frame = next(frames)
        except StopIteration:
            # If no patient frame was found, do not bother to continue.
            return

        for result_frame in frames:
            if result_frame[0:1] == b'L':
                break
            result_fields = Fields.from_string(delimiters, result_frame)
            self._process_lis2a2_result(result_fields)

    def parse_lis2a2_messages(self):
        """
        This is normally implemented as a FSM, which walks
        through the various states, which can deal with error recovery.

        I've simplified this a bit, and it now procedurally walks through
        establishment phase, transfer phase and then termination phase. And
        if an error occurs anywhere, it is fatal.
        """

        # Not sure if this first EOT is needed.
#        self._write_lis1a_frame(ASCII_EOT)

        data = self._read_lis1a_frame()
        if data == ASCII_ENQ:
            # LIS1-A 6.2.5
            self._write_lis1a_frame(ASCII_ACK)
        else:
            raise InvalidResponse(data)

        # LIS1-A 6.3 - Now we move to the transfer phase
        frames = self._parse_lis1a_transfer_frames(data)

        # Already start processing the LIS2-A2 message.
        self._parse_lis2a2_message(iter(frames))

        # LIS1-A 6.4 - Termination phase
        data = self._read_lis1a_frame()
        if data != ASCII_EOT:
            raise InvalidResponse(data)
