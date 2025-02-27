import struct
import time
from collections import namedtuple
from micropython import const

class CBits:
    """
    Changes bits from a byte register
    """

    def __init__(
        self,
        num_bits: int,
        register_address: int,
        start_bit: int,
        register_width=1,
        lsb_first=True,
    ) -> None:
        self.bit_mask = ((1 << num_bits) - 1) << start_bit
        self.register = register_address
        self.star_bit = start_bit
        self.lenght = register_width
        self.lsb_first = lsb_first

    def __get__(
        self,
        obj,
        objtype=None,
    ) -> int:
        mem_value = obj._i2c.readfrom_mem(obj._address, self.register, self.lenght)

        reg = 0
        order = range(len(mem_value) - 1, -1, -1)
        if not self.lsb_first:
            order = reversed(order)
        for i in order:
            reg = (reg << 8) | mem_value[i]

        reg = (reg & self.bit_mask) >> self.star_bit

        return reg

    def __set__(self, obj, value: int) -> None:
        memory_value = obj._i2c.readfrom_mem(obj._address, self.register, self.lenght)

        reg = 0
        order = range(len(memory_value) - 1, -1, -1)
        if not self.lsb_first:
            order = range(0, len(memory_value))
        for i in order:
            reg = (reg << 8) | memory_value[i]
        reg &= ~self.bit_mask

        value <<= self.star_bit
        reg |= value
        reg = reg.to_bytes(self.lenght, "big")

        obj._i2c.writeto_mem(obj._address, self.register, reg)


class RegisterStruct:
    """
    Register Struct
    """

    def __init__(self, register_address: int, form: str) -> None:
        self.format = form
        self.register = register_address
        self.lenght = struct.calcsize(form)

    def __get__(
        self,
        obj,
        objtype=None,
    ):
        if self.lenght <= 2:
            value = struct.unpack(
                self.format,
                memoryview(
                    obj._i2c.readfrom_mem(obj._address, self.register, self.lenght)
                ),
            )[0]
        else:
            value = struct.unpack(
                self.format,
                memoryview(
                    obj._i2c.readfrom_mem(obj._address, self.register, self.lenght)
                ),
            )
        return value

    def __set__(self, obj, value):
        mem_value = value.to_bytes(self.lenght, "big")
        obj._i2c.writeto_mem(obj._address, self.register, mem_value)

_REG_WHOAMI = const(0x0F)
_TEMP_RESULT = const(0x00)
_CONFIGURATION = const(0x01)
_TEMP_HIGH_LIMIT = const(0x02)
_TEMP_LOW_LIMIT = const(0x03)
_TEMP_OFFSET = const(0x07)

CONTINUOUS_CONVERSION_MODE = const(0b00)  # Continuous Conversion Mode
ONE_SHOT_MODE = const(0b11)  # One Shot Conversion Mode
SHUTDOWN_MODE = const(0b01)  # Shutdown Conversion Mode

_TMP117_RESOLUTION = const(0.0078125)

AlertStatus = namedtuple("AlertStatus", ["high_alert", "low_alert"])
ALERT_WINDOW = const(0)
ALERT_HYSTERESIS = const(1)

# Conversion Averaging Mode
AVERAGE_1X = const(0b00)
AVERAGE_8X = const(0b01)
AVERAGE_32X = const(0b10)
AVERAGE_64X = const(0b11)
averaging_measurements_values = (AVERAGE_1X, AVERAGE_8X, AVERAGE_32X, AVERAGE_64X)


class TMP117:
    """Main class for the Sensor

    :param ~machine.I2C i2c: The I2C bus the TMP117 is connected to.
    :param int address: The I2C device address. Defaults to :const:`0x48`

    :raises RuntimeError: if the sensor is not found


    **Quickstart: Importing and using the device**

    Here is an example of using the :class:`TMP117` class.
    First you will need to import the libraries to use the sensor

    .. code-block:: python

        from machine import Pin, I2C
        import micropython_tmp117 import tmp117

    Once this is done you can define your `machine.I2C` object and define your sensor object

    .. code-block:: python

        i2c = I2C(sda=Pin(8), scl=Pin(9))
        tmp117 = tmp117.TMP117(i2c)

    Now you have access to the :attr:`temperature` attribute

    .. code-block:: python

        temp = tmp117.temperature

    """

    _device_id = RegisterStruct(_REG_WHOAMI, ">H")
    _configuration = RegisterStruct(_CONFIGURATION, ">H")
    _raw_temperature = RegisterStruct(_TEMP_RESULT, ">h")
    _raw_temperature_offset = RegisterStruct(_TEMP_OFFSET, ">h")
    _raw_high_limit = RegisterStruct(_TEMP_HIGH_LIMIT, ">h")
    _raw_low_limit = RegisterStruct(_TEMP_LOW_LIMIT, ">h")

    # Register 0x01
    # HIGH_Alert|LOW_Alert|Data_Ready|EEPROM_Busy| MOD1(2) |   MOD0(1)    | CONV2(1) |CONV1(1)
    # ----------------------------------------------------------------------------------------
    # CONV0(1)  | AVG1(1) |AVG0(1)   |T/nA(1)    |POL(1)   |DR/Alert(1)   |Soft_Reset|   —
    _high_alert = CBits(1, _CONFIGURATION, 15, 2, False)
    _low_alert = CBits(1, _CONFIGURATION, 14, 2, False)
    _data_ready = CBits(1, _CONFIGURATION, 13, 2, False)
    _mode = CBits(2, _CONFIGURATION, 10, 2, False)
    _soft_reset = CBits(1, _CONFIGURATION, 1, 2, False)

    _conversion_averaging_mode = CBits(2, _CONFIGURATION, 5, 2, False)
    _conversion_cycle_bit = CBits(3, _CONFIGURATION, 7, 2, False)
    _raw_alert_mode = CBits(1, _CONFIGURATION, 4, 2, False)

    _avg_3 = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 4, 6: 8, 7: 16}
    _avg_2 = {0: 0.5, 1: 0.5, 2: 0.5, 3: 0.5, 4: 1, 5: 4, 6: 8, 7: 16}
    _avg_1 = {0: 0.125, 1: 0.125, 2: 0.25, 3: 0.5, 4: 1, 5: 4, 6: 8, 7: 16}
    _avg_0 = {0: 0.0155, 1: 0.125, 2: 0.25, 3: 0.5, 4: 1, 5: 4, 6: 8, 7: 16}
    _averaging_modes = {0: _avg_0, 1: _avg_1, 2: _avg_2, 3: _avg_3}

    def __init__(self, i2c, address=0x48) -> None:
        self._i2c = i2c
        self._address = address
        self._valide_range = range(-256, 255)

        if self._device_id != 0x117:
            raise RuntimeError("Failed to find TMP117!")

        self._reset = True
        # Following a reset, the temperature register reads –256 °C until the first
        # conversion, including averaging, is complete. So we sleep for that amount of time
        time.sleep(
            self._averaging_modes[self._conversion_averaging_mode][
                self._conversion_cycle_bit
            ]
        )
        self._mode = CONTINUOUS_CONVERSION_MODE
        while not self._data_ready:
            time.sleep(0.001)
        _ = self._raw_temperature * _TMP117_RESOLUTION

    @property
    def temperature(self) -> float:
        """
        The current measured temperature in Celsius
        Following a reset, the temperature reads -256 °C until the first conversion,
        including averaging, is complete. See the Power Up section in the datasheet
        for more information.
        """

        return self._raw_temperature * _TMP117_RESOLUTION

    @property
    def temperature_offset(self) -> float:
        """User defined temperature offset to be added to measurements from `temperature`.
        In order the see the new change in the temperature we need for the data to be ready.
        There is a time delay calculated according to current configuration.
        This is used as a user-defined temperature offset register during system calibration.
        The offset will be added to the temperature result after linearization. It has a same
        resolution of 7.8125 m°C and same range of ±256 °C as the temperature result register.
        If the added result is out of boundary, then the temperature result will show as the
        maximum or minimum value.

        .. code-block::python

            from machine import Pin, I2C
            import micropython_tmp117.tmp117 as tmp117

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            tmp = tmp117.TMP117(i2c)

            print("Temperature without offset: ", tmp.temperature)
            tmp117.temperature_offset = 10.0
            print("Temperature with offset: ", tmp.temperature)

        """
        return self._raw_temperature_offset * _TMP117_RESOLUTION

    @temperature_offset.setter
    def temperature_offset(self, value: float) -> None:
        self._raw_temperature_offset = self.validate_value(value)
        time.sleep(
            self._averaging_modes[self._conversion_averaging_mode][
                self._conversion_cycle_bit
            ]
        )

    @property
    def high_limit(self) -> float:
        """The high temperature limit in Celsius. When the measured temperature exceeds this
        value, the `high_alert` attribute of the `alert_status` property will be True.
        The range is ±256 °C. Following power-up or a general-call reset, the high-limit
        register is loaded with the stored value from the EEPROM. The factory default reset
        value is 192 °C (0x6000)
        """

        return self._raw_high_limit * _TMP117_RESOLUTION

    @high_limit.setter
    def high_limit(self, value: float) -> None:
        self._raw_high_limit = self.validate_value(value)

    @property
    def low_limit(self) -> float:
        """The low  temperature limit in Celsius. When the measured temperature goes below
        this value, the `low_alert` attribute of the `alert_status` property will be True.
        The range is ±256 °C. Following power-up or a general-call reset, the low-limit
        register is loaded with the stored value from the EEPROM. The factory default reset
        value is -256 °C (0x8000)
        """

        return self._raw_low_limit * _TMP117_RESOLUTION

    @low_limit.setter
    def low_limit(self, value: float) -> None:
        self._raw_low_limit = self.validate_value(value)

    def validate_value(self, value: int) -> int:
        """Validates for values to be in the range of :const:`-256` and :const:`255`,
        then return the value divided by the :const:`_TMP117_RESOLUTION`
        """
        if value not in self._valide_range:
            raise ValueError("Value should be within -256 and 255")
        return int(value / _TMP117_RESOLUTION)

    @property
    def alert_status(self) -> AlertStatus:
        """The current triggered status of the high and low temperature alerts as a AlertStatus
        named tuple with attributes for the triggered status of each alert.

        .. code-block :: python

            from machine import Pin, I2C
            import micropython_tmp117.tmp117 as tmp117

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            tmp = tmp117.TMP117(i2c)

            tmp.low_limit = 20
            tmp.high_limit = 23

            print("Alert mode:", tmp.alert_mode)
            print("High limit", tmp.high_limit)
            print("Low limit", tmp.low_limit)


            while True:
                print("Temperature: %.2f degrees C" % tmp.temperature)
                alert_status = tmp.alert_status
                if alert_status.high_alert:
                    print("Temperature above high set limit!")
                if alert_status.low_alert:
                    print("Temperature below low set limit!")
                print("Low alert:", alert_status.low_alert)
                time.sleep(1)

        """

        return AlertStatus(high_alert=self._high_alert, low_alert=self._low_alert)

    @property
    def alert_mode(self) -> str:
        """Sets the behavior of the `low_limit`, `high_limit`, and `alert_status` properties.

        When set to :py:const:`ALERT_WINDOW`, the `high_limit` property will unset when the
        measured temperature goes below `high_limit`. Similarly `low_limit` will be True or False
        depending on if the measured temperature is below (`False`) or above(`True`) `low_limit`.

        When set to :py:const:`ALERT_HYSTERESIS`, the `high_limit` property will be set to
        `False` when the measured temperature goes below `low_limit`. In this mode, the `low_limit`
        property of `alert_status` will not be set.

        The default is :py:const:`ALERT_WINDOW`

        +----------------------------------------+-------------------------+
        | Mode                                   | Value                   |
        +========================================+=========================+
        | :py:const:`tmp117.ALERT_WINDOW`        | :py:const:`0b0`         |
        +----------------------------------------+-------------------------+
        | :py:const:`tmp117.ALERT_HYSTERESIS`    | :py:const:`0b1`         |
        +----------------------------------------+-------------------------+

        """

        values = ("ALERT_WINDOW", "ALERT_HYSTERESIS")
        return values[self._raw_alert_mode]

    @alert_mode.setter
    def alert_mode(self, value: int) -> None:
        if value not in [0, 1]:
            raise ValueError("alert_mode must be set to 0 or 1")
        self._raw_alert_mode = value

    @property
    def averaging_measurements(self) -> str:
        """
        Users can configure the device to report the average of multiple temperature
        conversions with the :attr:`averaging_measurements` to reduce noise in the conversion
        results.
        When the TMP117 is configured to perform averaging with :attr:`averaging_measurements`
        set to :attr:`AVERAGE_8X`, the device executes the configured number of conversions to eight.
        The device accumulates those conversion results and reports the average of all the
        collected results at the end of the process.
        The average is an accumulated average and not a running average.

        +----------------------------------------+-------------------------+
        | Mode                                   | Value                   |
        +========================================+=========================+
        | :py:const:`tmp117.AVERAGE_1X`          | :py:const:`0b00`        |
        +----------------------------------------+-------------------------+
        | :py:const:`tmp117.AVERAGE_8X`          | :py:const:`0b01`        |
        +----------------------------------------+-------------------------+
        | :py:const:`tmp117.AVERAGE_32X`         | :py:const:`0b10`        |
        +----------------------------------------+-------------------------+
        | :py:const:`tmp117.AVERAGE_64X`         | :py:const:`0b11`        |
        +----------------------------------------+-------------------------+


        .. code-block::python3

            from machine import Pin, I2C
            import micropython_tmp117.tmp117 as tmp117

            i2c = I2C(sda=Pin(8), scl=Pin(9))  # Correct I2C pins for UM FeatherS2
            tmp = tmp117.TMP117(i2c)

            tmp.averaging_measurements = tmp117.AVERAGE_32X
            print("Averaging Measurements: ",tmp.averaging_measurements)

            while True:
                print("Temperature:", tmp.temperature)
                time.sleep(1)

        """

        values = ("AVERAGE_1X", "AVERAGE_8X", "AVERAGE_32X", "AVERAGE_64X")
        return values[self._conversion_averaging_mode]

    @averaging_measurements.setter
    def averaging_measurements(self, value: int) -> None:
        if value not in averaging_measurements_values:
            raise ValueError("Value must be a valid averaging_measurements setting")
        self._conversion_averaging_mode = value

    @property
    def measurement_mode(self) -> str:
        """Sets the measurement mode, specifying the behavior of how often measurements are taken.
                `measurement_mode` must be one of:

        When we use the sensor in One shot mode, the sensor will take the average_measurement value
        into account. However, this measure is done with the formula (15.5 ms x average_time), so in
        normal operation average_time will be 8, therefore time for measure is 124 ms.
        (See datasheet. 7.3.2 Averaging for more information). If we use 64, time will be 15.5 x 65 = 992 ms,
        the standby time will decrease, but the measure is still under 1 Hz cycle.
        (See Fig 7.2 on the datasheet)

        +-----------------------------------------------+------------------------------------------------------+
        | Mode                                          | Behavior                                             |
        +===============================================+======================================================+
        | :py:const:`tmp117.CONTINUOUS_CONVERSION_MODE` | Measurements are made at the interval determined by  |
        |                                               | `averaging_measurements`.                            |
        |                                               | `temperature` returns the most recent measurement    |
        +-----------------------------------------------+------------------------------------------------------+
        | :py:const:`tmp117.SHUTDOWN_MODE`              | Take a single measurement with the current number of |
        |                                               | `averaging_measurements` and switch to               |
        |                                               | :py:const:`SHUTDOWN` when finished.                  |
        |                                               | `temperature` will return the new measurement until  |
        |                                               | `measurement_mode` is set to :py:const:`CONTINUOUS`  |
        |                                               | or :py:const:`ONE_SHOT` is                           |
        |                                               | set again.                                           |
        +-----------------------------------------------+------------------------------------------------------+
        | :py:const:`tmp117.ONE_SHOT_MODE`              | The sensor is put into a low power state and no new  |
        |                                               | measurements are taken.                              |
        |                                               | `temperature` will return the last measurement until |
        |                                               | a new `measurement_mode` is selected.                |
        +-----------------------------------------------+------------------------------------------------------+

        """

        sensor_modes = {
            0: "CONTINUOUS_CONVERSION_MODE",
            1: "SHUTDOWN_MODE",
            3: "ONE_SHOT_MODE",
        }
        return sensor_modes[self._mode]

    @measurement_mode.setter
    def measurement_mode(self, value: int) -> None:
        self._mode = value