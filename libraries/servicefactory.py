import gc
import sys
import asyncio

class ServiceFactory:
    def __init__(self, provider):
        self.componentTypes = list(sorted(self.__discover_components(), key=lambda component: component[2]))
        self.components = dict(self.__instantiate_components(provider))
        print("Scheduler components discovered: %s" % ', '.join([str(component) for component in self.componentTypes]))
    
    def __discover_components(self):
        for moduleName in sys.modules:
            for name, item in sys.modules[moduleName].__dict__.items():
                if self.__is_valid_component(item):
                    yield (moduleName + '.' + name, item, int(getattr(item, 'CREATION_PRIORITY', 0)))
    
    def __instantiate_components(self, provider):
        for componentName, componentType, componentPriority in self.componentTypes:
            component = componentType.create(provider)
            provider[componentName] = component
            yield (componentName, component)
    
    def __is_valid_component(self, component):
        return isinstance(component, type) and \
               callable(getattr(component, 'create', None)) and \
               callable(getattr(component, 'start', None)) and \
               callable(getattr(component, 'stop', None))
    
    async def run(self):
        await asyncio.gather(*[self.run_component(component[1]) for component in self.components.items()])
    
    async def run_component(self, component):      
        while True:
            try:
                await component.start()
            except Exception as e:
                print(e)
                await asyncio.sleep(1)
            finally:
                await component.stop()
            gc.collect()
