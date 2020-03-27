#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2019 The glucometerutils Authors
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
        "--text_cmd_type",
        action="store",
        type=int,
        default=0x60,
        help="Message type for text commands sent to the device.",
    )
    parser.add_argument(
        "--text_reply_type",
        action="store",
        type=int,
        default=0x60,
        help="Message type for text replies received from the device.",
    )
    parser.add_argument(
        "device", action="store", help="Path to the HID device to open."
    )

    parser.add_argument(
        "--vlog",
        action="store",
        required=False,
        type=int,
        help=(
            "Python logging level. See the levels at "
            "https://docs.python.org/3/library/logging.html#logging-levels"
        ),
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.vlog)

    session = freestyle.FreeStyleHidSession(
        None, args.device, args.text_cmd_type, args.text_reply_type
    )

    session.connect()

    while True:
        if sys.stdin.isatty():
            command = input(">>> ")
        else:
            command = input()
            print(f">>> {command}")

        try:
            print(session.send_text_command(bytes(command, "ascii")))
        except exceptions.InvalidResponse as error:
            print(f"! {error}")


if __name__ == "__main__":
    main()
