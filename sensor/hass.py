import ujson
import urequests

class Hass:
    url = None
    token = None

    def __init__(self, url, token):
        self.url = url
        self.token = token

    def send_update(self, state, unit, device_class, friendly_name, sensor):
        data = {
            "state": state,
            "attributes": {
                "device_class": device_class,
                "friendly_name": friendly_name
            }
        }
        
        if unit is not None:
            data['attributes']['unit_of_measurement'] = unit
            data['attributes']['state_class'] = "measurement"

        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json; charset=utf-8"
        }

        response = urequests.post(self.url + "/api/states/" + sensor, data=ujson.dumps(data).encode('utf-8'), headers=headers, timeout=5)
        if not response.status_code in [200, 201]:
            raise Exception("Status " + str(response.status_code) + ": " + response.text)
