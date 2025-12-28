import gauge
import utime
import asyncio
import textbox

class ThermostatDisplay:
    def __init__(self, display, hass, entity_id, event_bus=None):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id
        self.event_bus = event_bus

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.entities = dict()
        self.alpha = 0
        self.is_active = True
        
        # Track previous values for focus detection
        self.prev_temperature = None
        self.prev_hvac_action = None
        self.prev_state = None
    
    CREATION_PRIORITY = 1
    def create(provider):
        event_bus = provider.get('eventbus.EventBus') or provider.get('libraries.eventbus.EventBus')
        return ThermostatDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['thermostat']['entity_id'], event_bus)
    
    def entity_updated(self, entity_id, entity):
        should_request_focus = False
        
        if entity_id == self.entity_id and self.event_bus is not None:
            # Get new values
            new_temp = entity.get('a', {}).get('temperature')
            new_hvac = entity.get('a', {}).get('hvac_action')
            new_state = entity.get('s')
            
            # Check for changes
            if self.prev_temperature is not None and self.prev_temperature != new_temp:
                should_request_focus = True
            elif self.prev_hvac_action is not None and self.prev_hvac_action != new_hvac:
                should_request_focus = True
            elif self.prev_state is not None and self.prev_state != new_state:
                should_request_focus = True
            
            # Update our tracking variables
            self.prev_temperature = new_temp
            self.prev_hvac_action = new_hvac
            self.prev_state = new_state
        
        # Update entities
        self.entities[entity_id] = entity
        
        if should_request_focus:
            self.event_bus.publish('focus.request', {
                'instance': self,
                'hold_ms': 8000  # Show for 8 seconds when thermostat changes
            })
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        # For testing
        #while True:
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    async def update(self):
        if not self.is_active:
            return
        start_update_ms = utime.ticks_ms()
        await self.__update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"ThermostatDisplay: {update_time_ms}ms")

    async def __update(self):
        default_entity = dict(s = '0')
        thermostat_entity = self.entities.get(self.entity_id, default_entity)
        current_target = float(thermostat_entity['a']['temperature'])
        current_temperature = float(thermostat_entity['a']['current_temperature'])
        minimum_temperature = float(thermostat_entity['a']['min_temp'])
        maximum_temperature = float(thermostat_entity['a']['max_temp'])
        hvac_action = thermostat_entity['a'].get('hvac_action', '?')
        
        self.display.rect(0, 70, self.display_width, self.display_height - 70, 0x0000, True)
        
        groove_color = 0x8A03 if hvac_action == 'heating' else 0x4208
        notch_outline_color = 0xFB64 if hvac_action and hvac_action != 'off' else 0x0000
        position = (0, 70)
        size = (self.display_width, self.display_height - 70)
        gauge.draw_gauge(self.display, position, size, minimum_temperature, maximum_temperature, current_target, current_temperature, False, groove_color=groove_color, notch_outline_color=notch_outline_color)

        # Draw primary (target) and secondary (current) temperatures
        white_pen = 0xFFFF
        primary_height = size[1] * 0.85
        textbox.draw_textbox(self.display, f'{current_target:.1f}°', position[0], position[1], size[0], primary_height, color=white_pen, font='regular')
        secondary_text_y = position[1] + size[1] * 0.65
        secondary_text_height = size[1] * 0.2
        textbox.draw_textbox(self.display, f'{current_temperature:.1f}°', position[0], secondary_text_y, size[0], secondary_text_height, color=white_pen, font='regular')

        # HVAC action label just above main temperature
        textbox.draw_textbox(self.display, hvac_action, 0, 90, self.display_width, 20, color=0xFFFF, font='small')

        # Render only the thermostat region (below the time/temperature displays)
        self.display.update((0, 70, self.display_width, self.display_height - 70))
    
    async def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            await self.update()
