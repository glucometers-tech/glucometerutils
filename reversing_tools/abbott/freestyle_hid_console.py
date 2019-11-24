#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CLI tool to send messages through FreeStyle HID protocol."""

import argparse
import logging
import sys

from glucometerutils import exceptions
from glucometerutils.support import freestyle

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--text_cmd_type', action='store', type=int, default=0x60,
        help='Message type for text commands sent to the device.')
    parser.add_argument(
        '--text_reply_type', action='store', type=int, default=0x60,
        help='Message type for text replies received from the device.')
    parser.add_argument(
        'device', action='store',
        help='Path to the HID device to open.')

    parser.add_argument(
        '--vlog', action='store', required=False, type=int,
        help=('Python logging level. See the levels at '
              'https://docs.python.org/3/library/logging.html#logging-levels'))

    args = parser.parse_args()

    logging.basicConfig(level=args.vlog)

    device = freestyle.FreeStyleHidDevice(args.device)
    device.TEXT_CMD = args.text_cmd_type
    device.TEXT_REPLY_CMD = args.text_reply_type

    device.connect()

    while True:
        if sys.stdin.isatty():
            command = input('>>> ')
        else:
            command = input()
            print('>>> {command}'.format(command=command))

        try:
            print(device._send_text_command(bytes(command, 'ascii')))
        except exceptions.InvalidResponse as error:
            print('! {error}'.format(error=error))

if __name__ == "__main__":
    main()
