# WLED Specification

This document outlines the specification for WLED, focusing on its APIs, effects, and internal data structures.

## APIs

WLED exposes a RESTful API for controlling the device.

### HTTP API

The primary way to interact with WLED is through its HTTP API. The API is controlled by sending GET requests to the `/win` endpoint with query parameters.

**Endpoint:** `/win`

**Method:** `GET`

#### Parameters

The following is a list of parameters that can be used to control WLED. This list is based on the `handleSet` function in `wled00/set.cpp` and should be considered comprehensive.

##### Segments
*   **`SM`**: `int` - Sets the main segment.
*   **`SS`**: `int` - Selects a single segment for control.
*   **`SV`**: `int` - Sets the selected state of a segment. `0` = off, `1` = on, `2` = unselect others.
*   **`S`**: `int` - Sets the start LED of a segment.
*   **`S2`**: `int` - Sets the stop LED of a segment.
*   **`GP`**: `int` - Sets the grouping of a segment.
*   **`SP`**: `int` - Sets the spacing of a segment.
*   **`RV`**: `bool` - Reverses the direction of a segment.
*   **`MI`**: `bool` - Mirrors a segment.
*   **`SB`**: `int` - Sets the brightness/opacity of a segment (0-255).
*   **`SW`**: `int` - Toggles the power of a segment. `0` = off, `1` = on, `2` = toggle.

##### Presets
*   **`PS`**: `int` - Saves the current state to a preset slot.
*   **`P1`**: `int` - Sets the first preset for a cycle.
*   **`P2`**: `int` - Sets the last preset for a a cycle.
*   **`PL`**: `int` - Applies a preset.
*   **`NP`**: - Advances to the next preset in a playlist.

##### Brightness & Color
*   **`A`**: `int` - Sets the master brightness (0-255).
*   **`R`**: `int` - Sets the red color channel (0-255).
*   **`G`**: `int` - Sets the green color channel (0-255).
*   **`B`**: `int` - Sets the blue color channel (0-255).
*   **`W`**: `int` - Sets the white color channel (0-255).
*   **`R2`**: `int` - Sets the secondary red color channel (0-255).
*   **`G2`**: `int` - Sets the secondary green color channel (0-255).
*   **`B2`**: `int` - Sets the secondary blue color channel (0-255).
*   **`W2`**: `int` - Sets the secondary white color channel (0-255).
*   **`LX`**: `int` - Sets the primary color using a Loxone value.
*   **`LY`**: `int` - Sets the secondary color using a Loxone value.
*   **`HU`**: `int` - Sets the hue of the primary color (0-65535).
*   **`SA`**: `int` - Sets the saturation of the primary color (0-255).
*   **`H2`**: - If present, `HU` and `SA` apply to the secondary color.
*   **`K`**: `int` - Sets the color temperature in Kelvin.
*   **`K2`**: - If present, `K` applies to the secondary color.
*   **`CL`**: `string` - Sets the primary color from a hex string or 32-bit decimal.
*   **`C2`**: `string` - Sets the secondary color from a hex string or 32-bit decimal.
*   **`C3`**: `string` - Sets the tertiary color from a hex string or 32-bit decimal.
*   **`SR`**: `int` - Sets a random color. `0` for primary, `1` for secondary.
*   **`SC`**: - Swaps the primary and secondary colors.

##### Effects
*   **`FX`**: `int` - Sets the effect ID.
*   **`FXD`**: - If present, applies the default settings for the effect.
*   **`SX`**: `int` - Sets the effect speed (0-255).
*   **`IX`**: `int` - Sets the effect intensity (0-255).
*   **`FP`**: `int` - Sets the color palette ID.
*   **`X1`**: `int` - Sets the custom effect parameter 1.
*   **`X2`**: `int` - Sets the custom effect parameter 2.
*   **`X3`**: `int` - Sets the custom effect parameter 3.
*   **`M1`**: `bool` - Sets the custom effect checkbox 1.
*   **`M2`**: `bool` - Sets the custom effect checkbox 2.
*   **`M3`**: `bool` - Sets the custom effect checkbox 3.

##### Overlays
*   **`OL`**: `int` - Sets the advanced overlay.

##### Macros
*   **`M`**: `int` - Applies a macro (deprecated).

##### Network
*   **`SN`**: `bool` - Toggles sending UDP direct notifications.
*   **`RN`**: `bool` - Toggles receiving UDP direct notifications.
*   **`RD`**: `bool` - Toggles receiving live data via UDP/Hyperion.

##### Power & Nightlight
*   **`T`**: `int` - Toggles the main power. `0` = off, `1` = on, `2` = toggle.
*   **`NL`**: `int` - Toggles the nightlight. `0` = off, `>0` = on with duration in minutes.
*   **`ND`**: - If present, uses the default nightlight duration.
*   **`NT`**: `int` - Sets the nightlight target brightness.
*   **`NF`**: `int` - Sets the nightlight fade mode.

##### Time & Timers
*   **`TT`**: `int` - Sets the transition delay.
*   **`ST`**: `int` - Sets the time from a Unix timestamp.
*   **`CT`**: `int` - Sets the countdown goal from a Unix timestamp.

##### Realtime
*   **`LO`**: `int` - Sets the realtime override mode.

##### System
*   **`RB`**: - Reboots the device.
*   **`NM`**: `bool` - Sets the clock mode. `0` = normal, `1` = countdown.
*   **`U0`**: `int` - Sets user variable 0.
*   **`U1`**: `int` - Sets user variable 1.
*   **`IN`**: - Internal call, does not send an XML response.
*   **`NN`**: - Suppresses UDP notifications for this request.

**Example:**

To set the color to red and the brightness to 128, you would send the following request:

`http://<wled-ip>/win?A=128&R=255&G=0&B=0`

### JSON API

In addition to the HTTP GET API, WLED exposes a more powerful JSON-based API. It is recommended to use the JSON API for new integrations. The JSON API is available at the `/json` endpoint.

**Endpoint:** `/json`

**Method:** `POST`

**Body:** A JSON object containing the desired state.

The following is a list of the main keys that can be used in the JSON object:

*   **`on`**: `bool` - Toggles the light on or off. Can also be the string "t" to toggle.
*   **`bri`**: `int` - Sets the master brightness (0-255).
*   **`transition`**: `int` - Sets the transition time in 100ms units.
*   **`tt`**: `int` - Sets the transition time in 100ms units. This is a temporary transition that is not saved.
*   **`ps`**: `int` - Sets the current preset.
*   **`psave`**: `int` - Saves the current state to a preset slot.
*   **`pdel`**: `int` - Deletes a preset.
*   **`playlist`**: `object` - Sets the current playlist.
*   **`nl`**: `object` - Nightlight settings.
    *   **`on`**: `bool` - Toggles the nightlight on or off.
    *   **`dur`**: `int` - The duration of the nightlight in minutes.
    *   **`mode`**: `int` - The nightlight mode.
    *   **`tbri`**: `int` - The target brightness of the nightlight.
*   **`udpn`**: `object` - UDP notification settings.
    *   **`send`**: `bool` - Toggles sending UDP notifications.
    *   **`sgrp`**: `int` - The UDP sync group for sending.
    *   **`rgrp`**: `int` - The UDP sync group for receiving.
*   **`lor`**: `int` - Live override.
*   **`live`**: `bool` - Toggles live mode.
*   **`mainseg`**: `int` - The main segment.
*   **`seg`**: `array` - An array of segment objects. See below for details.

#### Segment Object

Each object in the `seg` array can contain the following keys:

*   **`id`**: `int` - The segment ID.
*   **`start`**: `int` - The starting LED index.
*   **`stop`**: `int` - The ending LED index.
*   **`len`**: `int` - The length of the segment.
*   **`grp`**: `int` - The number of LEDs to group together.
*   **`spc`**: `int` - The number of LEDs to skip between each group.
*   **`rpt`**: `bool` - Repeat the segment until the end of the strip.
*   **`si`**: `int` - Sound simulation type.
*   **`m12`**: `int` - 1D to 2D mapping.
*   **`set`**: `int` - UI segment set/group.
*   **`of`**: `int` - The offset for the effect.
*   **`on`**: `bool` - Toggles the segment on or off.
*   **`frz`**: `bool` - Toggles freezing the segment.
*   **`bri`**: `int` - The segment brightness (0-255).
*   **`cct`**: `int` - The correlated color temperature of the segment (0-255).
*   **`col`**: `array` - An array of colors. Each color can be a hex string or an array of RGB(W) values.
*   **`fx`**: `int` - The effect ID.
*   **`sx`**: `int` - The effect speed (0-255).
*   **`ix`**: `int` - The effect intensity (0-255).
*   **`pal`**: `int` - The color palette ID.
*   **`sel`**: `bool` - Toggles selecting the segment.
*   **`rev`**: `bool` - Toggles reversing the segment.
*   **`mi`**: `bool` - Toggles mirroring the segment.
*   **`rY`**: `bool` - Reverses the Y-axis (2D).
*   **`mY`**: `bool` - Mirrors the Y-axis (2D).
*   **`tp`**: `bool` - Transposes X and Y axes (2D).
*   **`lx`**: `int` - Sets primary color from Loxone value.
*   **`ly`**: `int` - Sets secondary color from Loxone value.
*   **`fxdef`**: `bool` - Load effect defaults.
*   **`bm`**: `int` - Blending mode.
*   **`o1`**, **`o2`**, **`o3`**: `bool` - Custom effect checkboxes.
*   **`c1`**, **`c2`**: `int` - Custom effect parameters.
*   **`c3`**: `int` - Custom effect parameter (0-31).
*   **`n`**: `string` - The name of the segment.
*   **`i`**: `array` - An array of individual LED colors.

**Example:**

To set the color to red and the brightness to 128, you would send the following request:

```json
{
  "bri": 128,
  "seg": [{
    "col": [[255, 0, 0]]
  }]
}
```

The JSON API supports all the parameters of the HTTP API and many more.

### Other JSON Endpoints

In addition to the main `/json` endpoint, WLED exposes several other endpoints for retrieving specific information in JSON format:

*   **/json/info**: Returns information about the device, such as the version, MAC address, and LED configuration.
*   **/json/state**: Returns the current state of the device.
*   **/json/si**: Returns both state and info objects.
*   **/json/eff**: Returns a list of all available effects.
*   **/json/pal**: Returns a list of all available color palette names.
*   **/json/palx**: Returns a paginated list of all available color palettes with their color data.
*   **/json/fxda**: Returns effect data.
*   **/json/live**: Returns a live view of the LEDs.
*   **/json/nodes**: Returns a list of other WLED devices on the network.
*   **/json/net**: Returns a list of available Wi-Fi networks.
*   **/json/cfg**: Returns the device configuration.

These endpoints are useful for building integrations that require specific information about the device or its capabilities.

## Effects

WLED includes a wide variety of built-in effects. The following is a list of the available effects and their corresponding IDs.

| ID  | Name                      |
| --- | ------------------------- |
| 0   | Static                    |
| 1   | Blink                     |
| 2   | Breath                    |
| 3   | Color Wipe                |
| 4   | Color Wipe Random         |
| 5   | Random Color              |
| 6   | Color Sweep               |
| 7   | Dynamic                   |
| 8   | Rainbow                   |
| 9   | Rainbow Cycle             |
| 10  | Scan                      |
| 11  | Dual Scan                 |
| 12  | Fade                      |
| 13  | Theater Chase             |
| 14  | Theater Chase Rainbow     |
| 15  | Running Lights            |
| 16  | Saw                       |
| 17  | Twinkle                   |
| 18  | Dissolve                  |
| 19  | Dissolve Random           |
| 20  | Sparkle                   |
| 21  | Flash Sparkle             |
| 22  | Hyper Sparkle             |
| 23  | Strobe                    |
| 24  | Strobe Rainbow            |
| 25  | Multi Strobe              |
| 26  | Blink Rainbow             |
| 27  | Android                   |
| 28  | Chase Color               |
| 29  | Chase Random              |
| 30  | Chase Rainbow             |
| 31  | Chase Flash               |
| 32  | Chase Flash Random        |
| 33  | Chase Rainbow White       |
| 34  | Colorful                  |
| 35  | Traffic Light             |
| 36  | Color Sweep Random        |
| 37  | Running Color             |
| 38  | Aurora                    |
| 39  | Running Random            |
| 40  | Larson Scanner            |
| 41  | Comet                     |
| 42  | Fireworks                 |
| 43  | Rain                      |
| 44  | Tetrix                    |
| 45  | Fire Flicker              |
| 46  | Gradient                  |
| 47  | Loading                   |
| 48  | Rolling Balls             |
| 49  | Fairy                     |
| 50  | Two Dots                  |
| 51  | Fairytwinkle              |
| 52  | Running Dual              |
| 53  | Image                     |
| 54  | Tricolor Chase            |
| 55  | Tricolor Wipe             |
| 56  | Tricolor Fade             |
| 57  | Lightning                 |
| 58  | ICU                       |
| 59  | Multi Comet               |
| 60  | Dual Larson Scanner       |
| 61  | Random Chase              |
| 62  | Oscillate                 |
| 63  | Pride 2015                |
| 64  | Juggle                    |
| 65  | Palette                   |
| 66  | Fire 2012                 |
| 67  | Colorwaves                |
| 68  | BPM                       |
| 69  | Fillnoise8                |
| 70  | Noise16 1                 |
| 71  | Noise16 2                 |
| 72  | Noise16 3                 |
| 73  | Noise16 4                 |
| 74  | Colortwinkle              |
| 75  | Lake                      |
| 76  | Meteor                    |
| 77  | Copy                      |
| 78  | Railway                   |
| 79  | Ripple                    |
| 80  | Twinklefox                |
| 81  | Twinklecat                |
| 82  | Halloween Eyes            |
| 83  | Static Pattern            |
| 84  | Tri Static Pattern        |
| 85  | Spots                     |
| 86  | Spots Fade                |
| 87  | Glitter                   |
| 88  | Candle                    |
| 89  | Starburst                 |
| 90  | Exploding Fireworks       |
| 91  | Bouncingballs             |
| 92  | Sinelon                   |
| 93  | Sinelon Dual              |
| 94  | Sinelon Rainbow           |
| 95  | Popcorn                   |
| 96  | Drip                      |
| 97  | Plasma                    |
| 98  | Percent                   |
| 99  | Ripple Rainbow            |
| 100 | Heartbeat                 |
| 101 | Pacifica                  |
| 102 | Candle Multi              |
| 103 | Solid Glitter             |
| 104 | Sunrise                   |
| 105 | Phased                    |
| 106 | Twinkleup                 |
| 107 | Noisepal                  |
| 108 | Sinewave                  |
| 109 | Phasednoise               |
| 110 | Flow                      |
| 111 | Chunchun                  |
| 112 | Dancing Shadows           |
| 113 | Washing Machine           |
| 114 | 2D Plasma Rotozoom        |
| 115 | Blends                    |
| 116 | TV Simulator              |
| 117 | Dynamic Smooth            |
| 118 | 2D Spaceships             |
| 119 | 2D Crazybees              |
| 120 | 2D Ghostrider             |
| 121 | 2D Blobs                  |
| 122 | 2D Scrolltext             |
| 123 | 2D Driftrose              |
| 124 | 2D Distortionwaves        |
| 125 | 2D Soap                   |
| 126 | 2D Octopus                |
| 127 | 2D Wavingcell             |
| 128 | Pixels                    |
| 129 | Pixelwave                 |
| 130 | Juggles                   |
| 131 | Matripix                  |
| 132 | Gravimeter                |
| 133 | Plasmoid                  |
| 134 | Puddles                   |
| 135 | Midnoise                  |
| 136 | Noisemeter                |
| 137 | Freqwave                  |
| 138 | Freqmatrix                |
| 139 | 2D GEQ                    |
| 140 | Waterfall                 |
| 141 | Freqpixels                |
| 142 | Binmap                    |
| 143 | Noisefire                 |
| 144 | Puddlepeak                |
| 145 | Noisemove                 |
| 146 | 2D Noise                  |
| 147 | Perlinmove                |
| 148 | Ripplepeak                |
| 149 | 2D Firenoise              |
| 150 | 2D Squaredswirl           |
| 152 | 2D DNA                    |
| 153 | 2D Matrix                 |
| 154 | 2D Metaballs              |
| 155 | Freqmap                   |
| 156 | Gravcenter                |
| 157 | Gravcentric               |
| 158 | DJ Light                  |
| 159 | 2D Funkyplank             |
| 160 | Shimmer                   |
| 161 | 2D Pulser                 |
| 162 | Blurz                     |
| 163 | 2D Drift                  |
| 164 | 2D Waverly                |
| 165 | 2D Sunradiation           |
| 166 | 2D Coloredbursts          |
| 167 | 2D Julia                  |
| 172 | 2D Gameoflife             |
| 173 | 2D Tartan                 |
| 174 | 2D Polarlights            |
| 175 | 2D Swirl                  |
| 176 | 2D Lissajous              |
| 177 | 2D Frizzles               |
| 178 | 2D Plasmaball             |
| 179 | Flowstripe                |
| 180 | 2D Hipnotic               |
| 181 | 2D Sindots                |
| 182 | 2D Dnasprial              |
| 183 | 2D Blackhole              |
| 184 | Wavesins                  |
| 185 | Rocktaves                 |
| 186 | 2D Akemi                  |
| 187 | Particle Volcano          |
| 188 | Particle Fire             |
| 189 | Particle Fireworks        |
| 190 | Particle Vortex           |
| 191 | Particle Perlin           |
| 192 | Particle Pit              |
| 193 | Particle Box              |
| 194 | Particle Attractor        |
| 195 | Particle Impact           |
| 196 | Particle Waterfall        |
| 197 | Particle Spray            |
| 198 | Particle sGEQ             |
| 199 | Particle CenterGEQ        |
| 200 | Particle Ghostrider       |
| 201 | Particle Blobs            |
| 202 | PS Drip                   |
| 203 | PS Pinball                |
| 204 | PS Dancing Shadows        |
| 205 | PS Fireworks 1D           |
| 206 | PS Sparkler               |
| 207 | PS Hourglass              |
| 208 | PS 1D Spray               |
| 209 | PS Balance                |
| 210 | PS Chase                  |
| 211 | PS Starburst              |
| 212 | PS 1D GEQ                 |
| 213 | PS Fire 1D                |
| 214 | PS 1D Sonic Stream        |
| 215 | PS 1D Sonic Boom          |
| 216 | PS 1D Springy             |
| 217 | Particle Galaxy           |

## Data Structures

### Segments

WLED allows for the creation of segments, which are logical divisions of the LED strip. Each segment can have its own effect, color, and other settings. The segment data structure is defined in `wled00/FX.h` as the `Segment` class.

#### Segment Class

The `Segment` class contains the following important members:

*   **`start`**: `uint16_t` - The starting LED index of the segment.
*   **`stop`**: `uint16_t` - The ending LED index of the segment. A `stop` value of 0 marks the segment as inactive.
*   **`startY`**: `uint16_t` - The starting Y coodrinate 2D (top).
*   **`stopY`**: `uint16_t` - The ending Y coodrinate 2D (bottom).
*   **`offset`**: `uint16_t` - Offset for the effect.
*   **`speed`**: `uint8_t` - The effect speed (0-255).
*   **`intensity`**: `uint8_t` - The effect intensity (0-255).
*   **`palette`**: `uint8_t` - The color palette ID.
*   **`mode`**: `uint8_t` - The effect ID for the segment.
*   **`options`**: `uint16_t` - A bitmask of segment options. See [Segment Options](#segment-options) for details.
*   **`grouping`**: `uint8_t` - The number of LEDs to group together.
*   **`spacing`**: `uint8_t` - The number of LEDs to skip between each group.
*   **`opacity`**: `uint8_t` - The opacity of the segment (0-255).
*   **`cct`**: `uint8_t` - The correlated color temperature of the segment (0-255).
*   **`custom1`, `custom2`**: `uint8_t` - Custom effect parameters.
*   **`custom3`**: `uint8_t` (5 bits) - Custom effect parameter (0-31).
*   **`check1`, `check2`, `check3`**: `bool` - Custom effect checkboxes.
*   **`blendMode`**: `uint8_t` - The segment blending mode.
*   **`colors`**: `uint32_t[3]` - An array of 3 `uint32_t` values representing the primary, secondary, and tertiary colors of the segment. The colors are in RGBW format.
*   **`name`**: `char*` - The name of the segment.
*   **`data`**: `byte*` - A pointer to effect-specific data.

### Segment Options

The `options` member of the `Segment` class is a bitmask that controls various aspects of the segment's behavior. The following table describes the available options:

| Bit | Name          | Description                                           |
| --- | ------------- | ----------------------------------------------------- |
| 0   | `selected`    | If set, the segment is selected in the UI.            |
| 1   | `reverse`     | If set, the effect is reversed.                       |
| 2   | `on`          | If set, the segment is on.                            |
| 3   | `mirror`      | If set, the effect is mirrored.                       |
| 4   | `freeze`      | If set, the effect is frozen/paused.                  |
| 5   | `reset`       | If set, the segment's runtime is reset.               |
| 6   | `reverse_y`   | If set, the effect is reversed on the Y-axis (2D).    |
| 7   | `mirror_y`    | If set, the effect is mirrored on the Y-axis (2D).    |
| 8   | `transpose`   | If set, the X and Y axes are swapped (2D).            |
| 9-11| `map1D2D`     | Mapping for 1D effects on 2D panels.                  |
| 12-13| `soundSim`    | Sound simulation type.                                |
| 14-15| `set`         | UI segment sets/groups.                               |

### WS2812FX Class

The `WS2812FX` class is the main class for controlling the LED strip. It contains the following important members:

*   **`_segments`**: `std::vector<Segment>` - A vector of `Segment` objects.
*   **`_brightness`**: `uint8_t` - The master brightness of the strip.
*   **`_transitionDur`**: `uint16_t` - The duration of the transition between effects in milliseconds.
*   **`_modeCount`**: `uint8_t` - The number of registered effects.

### Panels

WLED supports 2D matrices, which are configured as a series of panels. The `Panel` struct is defined in `wled00/FX.h` and contains the following members:

*   **`xOffset`**: `uint16_t` - The X offset of the panel in LEDs.
*   **`yOffset`**: `uint16_t` - The Y offset of the panel in LEDs.
*   **`width`**: `uint8_t` - The width of the panel in LEDs.
*   **`height`**: `uint8_t` - The height of the panel in LEDs.
*   **`options`**: `uint8_t` - A bitmask of panel options. See [Panel Options](#panel-options) for details.

### Panel Options

The `options` member of the `Panel` struct is a bitmask that controls various aspects of the panel's behavior. The following table describes the available options:

| Bit | Name          | Description                                           |
| --- | ------------- | ----------------------------------------------------- |
| 0   | `bottomStart` - If set, the panel starts at the bottom.
| 1   | `rightStart` - If set, the panel starts on the right.
| 2   | `vertical` - If set, the panel is vertical.
| 3   | `serpentine` - If set, the panel is serpentine.

### Constants

WLED uses a variety of constants to define its behavior. These constants are defined in `wled00/const.h`.

#### Call Modes

The `callMode` is used to specify the source of a state change notification.

| Value | Name                  | Description                                       |
| ----- | --------------------- | ------------------------------------------------- |
| 0     | `CALL_MODE_INIT`      | No updates on init, can be used to disable updates. |
| 1     | `CALL_MODE_DIRECT_CHANGE` | Direct change from a user interface.              |
| 2     | `CALL_MODE_BUTTON`    | Button press.                                     |
| 3     | `CALL_MODE_NOTIFICATION` | Incoming notification (UDP or DMX preset).        |
| 4     | `CALL_MODE_NIGHTLIGHT` | Nightlight progress.                              |
| 5     | `CALL_MODE_NO_NOTIFY` | Change state but do not send notifications (UDP). |
| 7     | `CALL_MODE_HUE`       | Change from a Philips Hue device.                 |
| 10    | `CALL_MODE_ALEXA`     | Change from Amazon Alexa.                         |
| 11    | `CALL_MODE_WS_SEND`   | Updates websocket only.                           |
| 12    | `CALL_MODE_BUTTON_PRESET` | Button/IR JSON preset/macro.                      |

#### Realtime Modes

The `realtimeMode` is used to specify the source of realtime data.

| Value | Name                   | Description                               |
| ----- | ---------------------- | ----------------------------------------- |
| 0     | `REALTIME_MODE_INACTIVE` | No realtime data is being received.       |
| 1     | `REALTIME_MODE_GENERIC`  | Generic realtime data.                    |
| 2     | `REALTIME_MODE_UDP`      | UDP realtime data.                        |
| 3     | `REALTIME_MODE_HYPERION` | Hyperion realtime data.                   |
| 4     | `REALTIME_MODE_E131`     | E1.31 realtime data.                      |
| 5     | `REALTIME_MODE_ADALIGHT` | Adalight realtime data.                   |
| 6     | `REALTIME_MODE_ARTNET`   | Art-Net realtime data.                    |
| 7     | `REALTIME_MODE_TPM2NET`  | TPM2.NET realtime data.                   |
| 8     | `REALTIME_MODE_DDP`      | DDP realtime data.                        |
| 9     | `REALTIME_MODE_DMX`      | DMX realtime data.                        |

#### Realtime Override Modes

The `realtimeOverride` is used to specify how realtime data should be handled.

| Value | Name                     | Description                               |
| ----- | ------------------------ | ----------------------------------------- |
| 0     | `REALTIME_OVERRIDE_NONE`   | No override.                              |
| 1     | `REALTIME_OVERRIDE_ONCE`   | Override once.                            |
| 2     | `REALTIME_OVERRIDE_ALWAYS` | Always override.                          |

#### DMX Modes

The `DMXMode` is used to specify the DMX mode.

| Value | Name                    | Description                                       |
| ----- | ----------------------- | ------------------------------------------------- |
| 0     | `DMX_MODE_DISABLED`     | DMX is disabled.                                  |
| 1     | `DMX_MODE_SINGLE_RGB`   | All LEDs same RGB color (3 channels).             |
| 2     | `DMX_MODE_SINGLE_DRGB`  | All LEDs same RGB color and master dimmer (4 channels). |
| 3     | `DMX_MODE_EFFECT`       | Trigger standalone effects of WLED (15 channels). |
| 7     | `DMX_MODE_EFFECT_W`     | Trigger standalone effects of WLED (18 channels). |
| 4     | `DMX_MODE_MULTIPLE_RGB` | Every LED is addressed with its own RGB (ledCount * 3 channels). |
| 5     | `DMX_MODE_MULTIPLE_DRGB`| Every LED is addressed with its own RGB and share a master dimmer (ledCount * 3 + 1 channels). |
| 6     | `DMX_MODE_MULTIPLE_RGBW`| Every LED is addressed with its own RGBW (ledCount * 4 channels). |
| 8     | `DMX_MODE_EFFECT_SEGMENT` | Trigger standalone effects of WLED (15 channels per segment). |
| 9     | `DMX_MODE_EFFECT_SEGMENT_W` | Trigger standalone effects of WLED (18 channels per segment). |
| 10    | `DMX_MODE_PRESET`       | Apply presets (1 channel).                        |
