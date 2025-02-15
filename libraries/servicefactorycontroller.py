from management import OK_STATUS, HTML_HEADER, HEADER_TERMINATOR, MINIMAL_CSS, BACK_LINK, parse_form

class ServiceFactoryController:
    def __init__(self, servicefactory):
        self.servicefactory = servicefactory

    CREATION_PRIORITY = 1
    def create(provider):
        server = provider['management.ManagementServer']
        server.controllers.append(ServiceFactoryController(provider['servicefactory.ServiceFactory']))
        return None

    async def start(self):
        raise NotImplementedError
    
    def route(self, method, path):
        return path == b'/tasks'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        
        if b'cancel' in form:
            self.servicefactory.stop_component(form[b'cancel'].decode('ascii'))
        elif b'start' in form:
            asyncio.create_task(self.servicefactory.run_component_forever(form[b'start'].decode('ascii')))
        
        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<h1>Task Manager</h1>')
        writer.write(b'<table>')
        writer.write(b'<thead>')
        writer.write(b'<tr><th>Name</th><th>Running</th><th>Actions</th></tr>')
        writer.write(b'</thead>')
        writer.write(b'<tbody>')
        for componentName, component in self.servicefactory.components.items():
            task = self.servicefactory.tasks.get(componentName)
            task_running = not task.done() if task else False
            writer.write(b'<tr>')
            writer.write(b'<td>%s</td>' % componentName)
            writer.write(b'<td>%s</td>' % (b'&#x2713;' if task_running else b'&#x2717;'))
            writer.write(b'<td>')
            writer.write(b'<form action="" method="post"><input type="hidden" name="start" value="%s"/><button>Start</button></form>' % (componentName))
            writer.write(b'<form action="" method="post"><input type="hidden" name="cancel" value="%s"/><button>Cancel</button></form>' % (componentName))
            writer.write(b'</td>')
            writer.write(b'</tr>')
        writer.write(b'</tbody>')
        writer.write(b'</table>')
        writer.write(BACK_LINK)
