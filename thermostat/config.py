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
    entity_id = "<entity id>",
    occupancy_entity_id = "<optional entity id>",
    current_temperature_entity_id = "<optional entity id>",
    maximum_temperature_entity_id = "<optional entity id>",
    current_precipitation_entity_id = "<optional entity id>"
)

clock = dict(
    endpoint = "<time http endpoint>",
    update_time_ms = 300_000
)
