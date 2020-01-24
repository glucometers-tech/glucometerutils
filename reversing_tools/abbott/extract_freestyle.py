#!/usr/bin/env python3
#
# Copyright 2019 The usbmon-tools Authors
# Copyright 2020 The glucometerutils Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import logging
import sys

import usbmon
import usbmon.chatter
import usbmon.pcapng

HID_XFER_TYPES = (
    usbmon.constants.XferType.INTERRUPT,
    usbmon.constants.XferType.CONTROL,
)

def main():
    if sys.version_info < (3, 7):
        raise Exception(
            'Unsupported Python version, please use at least Python 3.7.')

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--addr_prefix', action='store', type=str, required=True,
        help=('Prefix match applied to the device address in text format. '
              'Only packets with source or destination matching this prefix '
              'will be printed out.'))

    parser.add_argument(
        '--vlog', action='store', required=False, type=int,
        help=('Python logging level. See the levels at '
              'https://docs.python.org/3/library/logging.html#logging-levels'))

    parser.add_argument(
        'pcap_file', action='store', type=str,
        help='Path to the pcapng file with the USB capture.')

    args = parser.parse_args()

    logging.basicConfig(level=args.vlog)

    session = usbmon.pcapng.parse_file(args.pcap_file, retag_urbs=False)
    for first, second in session.in_pairs():
        # Ignore stray callbacks/errors.
        if not first.type == usbmon.constants.PacketType.SUBMISSION:
            continue

        if not first.address.startswith(args.addr_prefix):
            # No need to check second, they will be linked.
            continue

        if first.xfer_type == usbmon.constants.XferType.INTERRUPT:
            pass
        elif (first.xfer_type == usbmon.constants.XferType.CONTROL and
              not first.setup_packet or
              first.setup_packet.type == usbmon.setup.Type.CLASS):
            pass
        else:
            continue

        if first.direction == usbmon.constants.Direction.OUT:
            packet = first
        else:
            packet = second

        if not packet.payload:
            continue

        assert len(packet.payload) >= 2

        message_length = packet.payload[1]

        # This is the case on Libre 2 (expected encrypted communication), in
        # which case we ignore the message_length and we keep the whole message
        # together.
        if message_length > 62:
            message_type = 'xx'
            message = packet.payload
        else:
            message_type = f'{packet.payload[0]:02x}'
            message = packet.payload[2:2+message_length]

        print(usbmon.chatter.dump_bytes(
            packet.direction,
            message,
            prefix=f'[{message_type}]',
            print_empty=True,
        ), '\n')


if __name__ == "__main__":
    main()
