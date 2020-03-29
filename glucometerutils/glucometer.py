#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2013 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Utility to manage glucometers' data."""

import argparse
import logging
import sys

from glucometerutils import common, driver, exceptions


def main():
    if sys.version_info < (3, 7):
        raise Exception("Unsupported Python version, please use at least Python 3.7")

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action")

    parser.add_argument(
        "--driver",
        action="store",
        required=True,
        help="Select the driver to use for connecting to the glucometer.",
    )
    parser.add_argument(
        "--device",
        action="store",
        required=False,
        help=(
            "Select the path to the glucometer device. Some devices require "
            "this argument, others will try autodetection."
        ),
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

    subparsers.add_parser(
        "help",
        help=(
            "Display a description of the driver, including "
            "supported features and known quirks."
        ),
    )
    subparsers.add_parser("info", help="Display information about the meter.")
    subparsers.add_parser("zero", help="Zero out the data log of the meter.")

    parser_dump = subparsers.add_parser(
        "dump", help="Dump the readings stored in the device."
    )
    parser_dump.add_argument(
        "--unit",
        action="store",
        choices=[unit.value for unit in common.Unit],
        help="Select the unit to use for the dumped data.",
    )
    parser_dump.add_argument(
        "--with-ketone",
        action="store_true",
        default=False,
        help="Enable ketone reading if available on the glucometer.",
    )

    parser_date = subparsers.add_parser(
        "datetime", help="Reads or sets the date and time of the glucometer."
    )
    parser_date.add_argument(
        "--set",
        action="store",
        nargs="?",
        const="now",
        default=None,
        help="Set the date rather than just reading it from the device.",
    )

    parser_patient = subparsers.add_parser(
        "patient", help="Reads or sets the patient information."
    )
    parser_patient.add_argument(
        "--set_name",
        action="store",
        required=False,
        help="Set the patient name, if the meter supports it.",
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.vlog)

    try:
        requested_driver = driver.load_driver(args.driver)
    except ImportError as e:
        logging.error(
            'Error importing driver "%s", please check your --driver parameter:\n%s',
            args.driver,
            e,
        )
        return 1

    # This check needs to happen before we try to initialize the device, as the help
    # action does not require a --device at all. Also use the same output if there's no
    # action provided.
    if not args.action or args.action == "help":
        print(requested_driver.help)
        return 0

    device = requested_driver.device(args.device)

    device.connect()
    device_info = device.get_meter_info()

    try:
        if args.action == "info":
            try:
                time_str = device.get_datetime()
            except exceptions.InvalidDateTime:
                time_str = "INVALID"
            # Also catch any leftover ValueErrors.
            except (NotImplementedError, ValueError):
                time_str = "N/A"
            print(f"{device_info}Time: {time_str}")
        elif args.action == "dump":
            unit = args.unit
            if unit is None:
                unit = device_info.native_unit

            readings = device.get_readings()

            if not args.with_ketone:
                readings = (
                    reading
                    for reading in readings
                    if not isinstance(reading, common.KetoneReading)
                )

            for reading in sorted(readings, key=lambda r: r.timestamp):
                print(reading.as_csv(unit))
        elif args.action == "datetime":
            if args.set == "now":
                print(device.set_datetime())
            elif args.set:
                try:
                    from dateutil import parser as date_parser

                    new_date = date_parser.parse(args.set)
                except ImportError:
                    logging.error(
                        'Unable to import module "dateutil", please install it.'
                    )
                    return 1
                except ValueError:
                    logging.error("%s: not a valid date", args.set)
                    return 1
                print(device.set_datetime(new_date))
            else:
                print(device.get_datetime())
        elif args.action == "patient":
            if args.set_name is not None:
                try:
                    device.set_patient_name(args.set_name)
                except NotImplementedError:
                    print("The glucometer does not support setting patient name.")
            try:
                patient_name = device.get_patient_name()
                if patient_name is None:
                    patient_name = "[N/A]"
                print(f"Patient Name: {patient_name}")
            except NotImplementedError:
                print("The glucometer does not support retrieving patient name.")
        elif args.action == "zero":
            confirm = input("Delete the device data log? (y/N) ")
            if confirm.lower() in ["y", "ye", "yes"]:
                device.zero_log()
                print("\nDevice data log zeroed.")
            else:
                print("\nDevice data log not zeroed.")
                return 1
        else:
            return 1
    except exceptions.Error as err:
        print(f"Error while executing '{args.action}': {err}")
        return 1

    device.disconnect()
    return 0
