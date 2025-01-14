# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2023 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for FreeStyle Libre 3 devices.

Supported features:
    The same as the fslibre driver.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

This driver is a shim on top of the fslibre driver, forcing encryption to be
enabled for the session and normalizing the returned records.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/abbott/freestyle-libre
https://protocols.glucometers.tech/abbott/freestyle-libre-2

"""

from collections.abc import Sequence
from typing import Optional

from glucometerutils.support import freestyle_libre


class Device(freestyle_libre.LibreDevice):
    _MODEL_NAME = "FreeStyle Libre 3"

    def __init__(self, device_path: Optional[str]) -> None:
        super().__init__(0x3960, device_path, encoding="utf-8", encrypted=True)

    @staticmethod
    def _normalize_history_record(record: Sequence[str]) -> Sequence[str]:
        """Overridden function as one of the unknown columns is missing."""
        record.insert(10, "0")
        return record

    @staticmethod
    def _normalize_result_record(record: Sequence[str]) -> Sequence[str]:
        """Overridden function as error values and custom comments are missing."""
        record.insert(19, "0")
        record.insert(28, 0)
        if len(record) > 29:
            record = record[:29] + 6*["\"\""] + record[29:]
        return record
