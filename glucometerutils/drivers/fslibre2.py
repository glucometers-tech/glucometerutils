# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: © 2023 The glucometerutils Authors
# SPDX-License-Identifier: MIT
"""Driver for FreeStyle Libre 2 devices.

Supported features:
    The same as the fslibre driver.

Expected device path: /dev/hidraw9 or similar HID device. Optional when using
HIDAPI.

This driver is a shim on top of the fslibre driver, forcing encryption to be
enabled for the session.

Further information on the device protocol can be found at

https://protocols.glucometers.tech/abbott/freestyle-libre
https://protocols.glucometers.tech/abbott/freestyle-libre-2

"""

from typing import Optional

from glucometerutils.support import freestyle_libre


class Device(freestyle_libre.LibreDevice):
    _MODEL_NAME = "FreeStyle Libre 2"

    def __init__(self, device_path: Optional[str]) -> None:
        super().__init__(0x3950, device_path, encoding="utf-8", encrypted=True)
