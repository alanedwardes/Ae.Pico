import asyncio
import textbox

class AlertDisplay:
    FOCUS_HOLD_MS = 86400000

    def __init__(self, display, hass, event_bus, entity_id, strobe_ms, start_y):
        self.display = display
        self.hass = hass
        self.event_bus = event_bus
        self.entity_id = entity_id
        self.strobe_ms = strobe_ms
        self.start_y = start_y
        self.message = ''
        self.has_received_state = False

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['alert']
        y_separator = provider['config']['display'].get('y_separator', 70)
        display = provider['display']
        return AlertDisplay(
            display,
            provider['hassws.HassWs'],
            provider['eventbus.EventBus'],
            config['entity_id'],
            config.get('strobe_ms', 1000),
            y_separator
        )

    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_changed)
        await asyncio.Event().wait()

    def entity_changed(self, entity_id, entity):
        is_initial = not self.has_received_state
        self.has_received_state = True

        state = entity.get('s') or ''
        if state == self.message:
            return

        self.message = state

        if is_initial:
            return

        if state:
            self.event_bus.publish('focus.request', {
                'instance': self,
                'hold_ms': self.FOCUS_HOLD_MS
            })
        else:
            self.event_bus.publish('focus.request')

    def should_activate(self):
        return bool(self.message)

    async def activate(self):
        inverted = False
        while self.message:
            self.render(inverted)
            inverted = not inverted
            await asyncio.sleep(self.strobe_ms / 1000)

    def update(self):
        if self.message:
            self.render(False)

    def render(self, inverted):
        background = 0xFFFFFF if inverted else 0x000000
        foreground = 0x000000 if inverted else 0xFFFFFF
        height = self.display.height - self.start_y

        self.display.rect(0, self.start_y, self.display.width, height, background, True)
        textbox.draw_textbox(self.display, self.message, 0, self.start_y, self.display.width, height, color=foreground, font='regular', wrap=True)
