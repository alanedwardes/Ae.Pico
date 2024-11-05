# Ae.Pico

A collection of Micropython libraries for the Raspberry Pi Pico W.

## ws.py

Provides async WebSocket connection with SSL support.

### Installation

```python
import mip
mip.install('github:alanedwardes/Ae.Pico/libraries/ws.py')
```

### Basic Usage

```python
import ws

socket = await ws.connect('wss://endpoint')

while True:
    message = await socket.recv()        
    if message is None:
        # Do nothing - this was a ping/pong response
        continue

    # Do something with message
    payload = json.loads(message)

    # Send something back
    await socket.send('{"test":true}')
```

## hassws.py

Home Assistant [WebSocket API](https://developers.home-assistant.io/docs/api/websocket/) support. Depends on [ws.py](#wspy).

### Installation

```python
import mip
mip.install('github:alanedwardes/Ae.Pico/libraries/ws.py')
mip.install('github:alanedwardes/Ae.Pico/libraries/hassws.py')
```

### Basic Usage

```python
import hassws
import network

nic = network.WLAN(network.STA_IF)

# HassWs polls the nic until there is a
# connection, before attempting to connect
hass = HassWs('ws://homeassistant', '<token>', nic)

def example_sensor_updated(entity_id, entity):
    if entity['s'] == 'on':
        # Do something if sensor is 'on'

# Subscribe to entity to get updates
hass.subscribe('sensor.example', example_sensor_updated)

while True:
    try:
        await hass.start()
    except:
        # Do something with exception
    finally:
        await hass.stop()

# Call an action
await hass.action('climate', 'set_temperature', {'temperature': 19}, 'climate.kitchen')
```
