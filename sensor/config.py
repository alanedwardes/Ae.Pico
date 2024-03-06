wifi = dict(
    ssid = "ssid",
    key = "key",
    host = "hostname"
)

hass = dict(
    url = "http://localhost",
    token = "<token>"
)

motion_sensor = dict(
    enabled = True,
    friendly_name = "Test Motion",
    name = "test_motion",
    timeout_ms = 900_000,
    pin = 22
)

bme280_sensor = dict(
    enabled = True,
    scl_pin = 1,
    sda_pin = 0,
    temp_friendly_name = "Test Temperature",
    temp_name = "test_temperature",
    pressure_friendly_name = "Test Pressure",
    pressure_name = "test_pressure",
    humidity_friendly_name = "Test Humidity",
    humidity_name = "test_humidity"
)

scd4x_sensor = dict(
    enabled = True,
    sda_pin = 0,
    scl_pin = 1,
    temp_friendly_name = "Test Temperature",
    temp_name = "test_temperature",
    co2_friendly_name = "Test Carbon Dioxide",
    co2_name = "test_co2",
    humidity_friendly_name = "Test Humidity",
    humidity_name = "test_humidity"
)
