class Touch:
    """
    Hardware-agnostic Touch abstraction.
    Provides a simple publish-subscribe interface for touch events.
    Injected as the 'touch' provider.
    """
    def __init__(self):
        self.subscribers = []
        self.current_point = None

    def subscribe(self, callback):
        """
        Add a callback to receive touch events. 
        Callback signature: func(tuple(x, y) or None)
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)

    def unsubscribe(self, callback):
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def dispatch(self, point):
        """Called by the hardware driver to push new touch events."""
        self.current_point = point
        # Copy the list to avoid issues if a subscriber unsubscribes during iteration
        for sub in list(self.subscribers):
            sub(point)

    @property
    def is_touched(self):
        return self.current_point is not None
