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

_KEEPALIVE_TYPE = 0x22

_UNENCRYPTED_TYPES = (
    0x01, 0x04, 0x05, 0x06, 0x0c, 0x0d,
    0x14, 0x15,
    0x33, 0x34, 0x35,
    0x71,
    _KEEPALIVE_TYPE,
)

_ABBOTT_VENDOR_ID = 0x1a61
_LIBRE2_PRODUCT_ID = 0x3950



def main():
    if sys.version_info < (3, 7):
        raise Exception(
            'Unsupported Python version, please use at least Python 3.7.')

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--device_address', action='store', type=str,
        help=('Device address (busnum.devnum) of the device to extract capture'
              'of. If none provided, device descriptors will be relied on.'))

    parser.add_argument(
        '--encrypted_protocol', action='store_true',
        help=('Whether to expect encrypted protocol in the capture.'
              ' Ignored if the device descriptors are present in the capture.'))

    parser.add_argument(
        '--vlog', action='store', required=False, type=int,
        help=('Python logging level. See the levels at '
              'https://docs.python.org/3/library/logging.html#logging-levels'))

    parser.add_argument(
        '--print_keepalive', action='store_true',
        help=('Whether to print the keepalive messages sent by the device. '
              'Keepalive messages are usually safely ignored.'))

    parser.add_argument(
        'pcap_file', action='store', type=str,
        help='Path to the pcapng file with the USB capture.')

    args = parser.parse_args()

    logging.basicConfig(level=args.vlog)

    session = usbmon.pcapng.parse_file(args.pcap_file, retag_urbs=False)

    if not args.device_address:
        for descriptor in session.device_descriptors.values():
            if descriptor.vendor_id == _ABBOTT_VENDOR_ID:
                if args.device_address and args.device_address != descriptor.address:
                    raise Exception(
                        'Multiple Abbott device present in capture, please'
                        ' provide a --device_address flag.')
                args.device_address = descriptor.address

    descriptor = session.device_descriptors.get(args.device_address, None)
    if not descriptor:
        logging.warning(
            f"Unable to find device %s in the capture's descriptors."
            " Assuming non-encrypted protocol.", args.device_address)
    else:
        assert descriptor.vendor_id == _ABBOTT_VENDOR_ID

    if descriptor and descriptor.product_id == _LIBRE2_PRODUCT_ID:
        args.encrypted_protocol = True

    for first, second in session.in_pairs():
        # Ignore stray callbacks/errors.
        if not first.type == usbmon.constants.PacketType.SUBMISSION:
            continue

        if not first.address.startswith(f'{args.device_address}.'):
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

        message_type = packet.payload[0]

        if message_type == _KEEPALIVE_TYPE and not args.print_keepalive:
            continue

        if args.encrypted_protocol and message_type not in _UNENCRYPTED_TYPES:
            # When expecting encrypted communication), we ignore the
            # message_length and we keep it with the whole message.
            message_type = f'x{message_type:02x}'
            message = packet.payload[1:]
        else:
            message_length = packet.payload[1]
            message_type = f' {message_type:02x}'
            message = packet.payload[2:2+message_length]

        print(usbmon.chatter.dump_bytes(
            packet.direction,
            message,
            prefix=f'[{message_type}]',
            print_empty=True,
        ), '\n')


if __name__ == "__main__":
    main()
