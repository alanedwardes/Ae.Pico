# Ae.Pico

A collection of Micropython libraries for the Raspberry Pi Pico.

## Areas

* [libraries](./libraries) - Various Micropython libraries including an async WebSockets client for Home Assistant (see [README](./libraries/README.md))
* [sensor](./sensor) - Async sensor routines for Home Assistant to report the status of various I2C/GPIO sensors
* [infodisplay](./infodisplay) - Informational display for Home Assistant (Pimoroni Pico Display Pack 2.0/2.8)

## Async Modules

This repository offers a standard async module layout to simplify running, configuring and deploying multiple disparate async modules in parallel, using a lightweight dependency injection system ([servicefactory.py](./libraries/servicefactory.py)).

Async modules are laid out in a standard way: they have a static `create` method accepting a `provider` parameter, and an async instance `start` method:

```python
class MyModule:
    def create(provider):
        # Factory method
        return MyModule()
    
    async def start(self):
        # Async work
```

The async `start` method is expected to run forever, and will be retried if it exits (e.g. throws an exception, or returns). The `start` method should also be expected to gracefully [cancel](https://docs.python.org/3/library/asyncio-task.html#task-cancellation).

### Example Basic Async Module
To deploy an example async module which prints to the console:
1. Copy [main.py](./main.py) to `main.py`
2. Copy [servicefactory.py](./libraries/servicefactory.py) to `lib/servicefactory.py`
2. Create `config.py` with the following:
```python
import mymodule

config = dict()
```
3. Create `mymodule.py` with the following:
```python
import asyncio

class MyModule:
    def create(provider):
        return MyModule()
    
    async def start(self):
        print('Started')
        while True:
            await asyncio.sleep(30)
            print('30s passed')
```
4. Run `main.py`. You should see the following:
```
Started
30s passed
30s passed
...
```
To deploy another async module, simply define it with a static `create` and async `start` method, and import it into `config.py`.

### Example Async Module with Dependency Injection

It is possible to inject config and services in the async module's `create` method. To prepare, make the following changes to `config.py`:

```python
import mymodule

config = dict(
    mymodule = dict(wait_ms = 1_000)
)
```

And copy the following adapted version of `mymodule.py`:

```python
import asyncio

class MyModule:
    def __init__(self, nic, wait_ms):
        self.nic = nic
        self.wait_ms = wait_ms
    
    def create(provider):
        config = provider['config']['mymodule']
        return MyModule(provider['nic'], config['wait_ms'])
    
    async def start(self):
        print('Started')       
        while True:
            await asyncio.sleep_ms(self.wait_ms)
            connected = self.nic.isconnected()
            net = 'connected' if connected else 'no network'
            print('%ims passed (%s)' % (self.wait_ms, net))
```

This newer version injects config to determine how long to wait, and also the network card to print the network status (both `config` and `nic` are basic services registered directly in `main.py`).

### Automatic Dependency Registration

All async modules are made available to the dependency injection container by default, accessible via their fully qualified name. Consider the following module:

```python
class MyModule:
    def create(provider):
        return MyModule()
    
    async def start(self):
        pass
    
    async def mymethod(self):
        raise NotImplementedError
```

This can be accessed automatically by another module's creation method by referring to it as `mymodule.MyModule`:

```python
class MyOtherModule:
    def __init__(self, mymodule):
        self.mymodule = mymodule

    CREATION_PRIORITY = 1
    def create(provider):
        return MyOtherModule(provider['mymodule.MyModule'])

    async def start(self):
        # Do something with the injected dependency
        await self.mymodule.mymethod()
```

Note that the second module has the following static property:
```python
CREATION_PRIORITY = 1
```

This is a hint to the dependency injection system about what order to initialize dependencies in; higher means later (making this explicit keeps the service factory simple and fast).

### Custom Dependency Registration

An async module may also register its own dependencies with custom names. This can be done by adding to the dependency injection container in an async module's `create` method:

```python
def create(provider):
    provider['myservice'] = MyService()
    return MyModule()

async def start(self):
    await asyncio.Event().wait()
```

This allows manipulation of the dependency injection container prior to construction of the module. If the start method doesn't ever need to be run, the `create` method can simply not return:

```python
def create(provider):
    provider['myservice'] = MyService()

async def start(self):
    raise NotImplementedError
```

In the above example, `start` will never be called, and `myservice` will be added to the dependency injection container. This allows async modules to manipulate the service container without changing the dependency injection container in `main.py`.
