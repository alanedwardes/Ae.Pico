# Info Display
These classes relate to rendering to a 320x240 pixel MicroPython framebuf object, often obtaining data from a REST API.

# Time Display & Temperature Display
![](../docs/time-temperature.png)

From left to right:
1. The time in 24 hour format
2. A two letter day abbreviation with the seconds below it
3. A guage with the current temperature at the centre, with the minimum temperature on the bottom left, and maximum temperature on the bottom right

# Weather Display
![](../docs/daily-weather.png)

From top to bottom:
1. Day of the week
2. Main weather icon for the day
3. The maximum temperature for the day
4. The minimum temperature for the day
5. The percentage chance of rain

# Rain Display
![](../docs/hourly-rain.png)

From top to boottom:
1. Hour of the day
2. Number of millimeters of rain for that hour
3. The percentage change of rain for that hour, visualized as a graph point
4. The Beaufort Wind Scale value for that hour