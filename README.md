# Ae.Pico

A collection of Micropython libraries for the Raspberry Pi Pico W.

## [ws.py](./libraries/ws.py)

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

## [hassws.py](./libraries/hassws.py)

Home Assistant [WebSocket API](https://developers.home-assistant.io/docs/api/websocket/) support. Depends on [ws.py](#wspy).

### Installation

```python
import mip
mip.install('github:alanedwardes/Ae.Pico/libraries/ws.py')
mip.install('github:alanedwardes/Ae.Pico/libraries/hassws.py')
```

### Basic Usage

```python
from hassws import HassWs
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

## [hass.py](./libraries/hass.py)

Home Assistant [REST API](https://developers.home-assistant.io/docs/api/rest/) support.

### Installation

```python
import mip
mip.install('github:alanedwardes/Ae.Pico/libraries/hass.py')
```

### Basic Usage

```python
from hass import Hass

# Init Home Assistant
hass = Hass('http://homeassistant', '<token>')

# Send sensor update
await hass.send_update(17, '°C"', 'temperature', 'Sensor Name', 'sensor.my_sensor_id')

# Render template
time = await hass.render_template('{{ now() }}')

# Set the RTC from Home Assistant's clock
await hass.set_time()
```

## [management.py](./libraries/management.py)

Simple HTTP management server with support for editing/uploading/downloading files, and rebooting.

### Installation

```python
import mip
mip.install('github:alanedwardes/Ae.Pico/libraries/management.py')
```

### Basic Usage

```python
import management

# Listen on port 80
server = management.ManagementServer(80)

# Optionally require HTTP basic auth
server.set_credentials('username', 'password')

while True:
    try:
        await server.start()
    except:
        # Do something with exception
    finally:
        await server.stop()
```