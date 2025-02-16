# Ae.Pico

A collection of Micropython libraries for the Raspberry Pi Pico.

## Areas

* [libraries](./libraries) - Various Micropython libraries including an async WebSockets client for Home Assistant (see [README](./libraries/README.md))
* [sensor](./sensor) - Async sensor routines for Home Assistant to report the status of various I2C/GPIO sensors
* [infodisplay](./infodisplay) - Informational display for Home Assistant (Pimoroni Pico Display Pack 2.0/2.8)
* [thermostat](./thermostat) - Integration with a Home Assistant thermostat (Pimoroni Pico Display Pack 2.0/2.8)

## Entry Point

All async routines leverage the same entry point, [main.py](./main.py) which requires `config.py` to be present which imports and configures the async routines to run. Here's an example config for a simple motion sensor:

### Example `config.py`

```python
# Config-driven robust WiFi connection
import wifi
# Expose an HTTP-based management server
import management
# Expose /tasks management endpoint
import servicefactorycontroller
# Configure the Home Assistant HTTP client
import hass
# Add the Home Assistant motion detection routine
import hassmotion

config = dict(
    wifi = dict(ssid = "<ssid>", key = "<key>", host = "<hostname>"),
    hass = dict(
        url = "http://<home assistant endpoint>",
        token = "<home assistant token>"
    ),
    motion = dict(
        friendly_name = "<motion sensor friendly name>",
        sensor = "binary_sensor.<motion sensor entity id>",
        pin = 0 # <pin the PIR sensor is connected to>
    )
)
```

Other modules are used in the same way, by importing them, and configuring them.
