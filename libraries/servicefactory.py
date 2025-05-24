import gc
import sys
import asyncio

class ServiceFactory:
    INSTANCE = None

    def __init__(self, provider):
        self.exception_handler = None
        # The last created instance gets a reference
        ServiceFactory.INSTANCE = self
        # Make this instance available to the service provider
        provider['%s.%s' % (self.__class__.__module__, self.__class__.__name__)] = self
        self.componentTypes = list(sorted(self.__discover_components(), key=lambda component: component[2]))
        self.components = dict(self.__instantiate_components(provider))
        self.tasks = dict()
        #print("%i scheduler components:\n* %s" % (len(self.components), '\n* '.join(self.components)))
        #print("%i service provider entries:\n* %s" % (len(provider), '\n* '.join(set(provider.keys()) - set(self.components.keys()))))

    def __discover_components(self):
        for moduleName in sys.modules:
            for name, item in sys.modules[moduleName].__dict__.items():
                if self.__is_valid_component(item):
                    yield (moduleName + '.' + name, item, int(getattr(item, 'CREATION_PRIORITY', 0)))

    def __instantiate_components(self, provider):
        for componentName, componentType, componentPriority in self.componentTypes:
            component = None
            
            try:
                component = componentType.create(provider)
            except Exception as e:
                print("Fatal error instantiating %s: %s" % (componentName, str(e)))
                self.exception_handler and self.exception_handler(e)

            if not component:
                #print("Component %s has no default export" % componentName)
                continue

            provider[componentName] = component
            yield (componentName, component)

    def __is_valid_component(self, component):
        return isinstance(component, type) and \
               callable(getattr(component, 'create', None)) and \
               callable(getattr(component, 'start', None))

    async def run_components_forever(self):
        await asyncio.gather(*[self.run_component_forever(componentName) for componentName in self.components.keys()])

    def stop_component(self, componentName):
        if not componentName in self.tasks:
            return

        self.tasks[componentName].cancel()
        del self.tasks[componentName]
        gc.collect()

    async def run_component_forever(self, componentName):
        while True:
            try:
                await self.run_component_once(componentName)
                await asyncio.sleep(1)
            except asyncio.CancelledError as e:
                break

    async def run_component_once(self, componentName):
        self.stop_component(componentName)

        try:
            self.tasks[componentName] = asyncio.create_task(self.components[componentName].start())
            await self.tasks[componentName]
        except Exception as e:
            print("Exception from %s: %s" % (componentName, str(e)))
            self.exception_handler and self.exception_handler(e)
        finally:
            gc.collect()
