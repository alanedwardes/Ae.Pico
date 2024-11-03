wifi = dict(
    ssid = "ssid",
    key = "key",
    host = "hostname"
)

hass = dict(
    url = "http://localhost",
    token = "<token>"
)

thermostat = dict(
    rotate = 0,
    leds = (6, 7, 8),
    entity_id = "<entity id>",
    occupancy_entity_id = "<optional entity id>",
    middle_row = [
        dict(entity_id = '<thermostat entity id>', attribute = 'current_temperature', label = 'now', format = lambda x: '%.1fc' % float(x), temperature = True),
        dict(entity_id = '<thermostat entity id>', attribute = 'temperature', label = 'target', format = lambda x: '%.1fc' % float(x), temperature = True)
    ],
    bottom_row = [
        dict(entity_id = '<current weather entity id>', label = 'now', format = lambda x: '%.0fc' % float(x), temperature = True),
        dict(entity_id = '<current rain chance entity id>', label = 'rain', format = lambda x: '%.0f%%' % float(x))
    ]
)

clock = dict(
    endpoint = "<time http endpoint>",
    update_time_ms = 300_000
)
