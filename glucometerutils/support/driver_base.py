from abc import ABC, abstractmethod
from datetime import datetime


class GlucometerDriver(ABC):
    def connect(self):
        pass

    def disconnect(self):
        pass

    @abstractmethod
    def get_meter_info(self):
        """Return the device information in structured form."""
        pass

    @abstractmethod
    def get_serial_number(self):
        pass

    @abstractmethod
    def get_glucose_unit(self):
        """Returns the glucose unit of the device."""
        pass

    @abstractmethod
    def get_datetime(self):
        pass

    def set_datetime(self, date=None):
        """Sets the date and time of the glucometer.

        Args:
          date: The value to set the date/time of the glucometer to. If none is
            given, the current date and time of the computer is used.

        Returns:
          A datetime object built according to the returned response.
        """
        if not date:
            date = datetime.now()
        return self._set_device_datetime(date)

    @abstractmethod
    def _set_device_datetime(self, date):
        pass

    @abstractmethod
    def zero_log(self):
        pass

    @abstractmethod
    def get_readings(self):
        pass
