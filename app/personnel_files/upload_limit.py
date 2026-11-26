"""Bound the multipart request before Starlette spools an unlimited upload to disk."""
from app.personnel_files.storage import MAX_BYTES


class PersonnelFileUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        guarded = path.startswith('/api/personnel-files/') or (path.startswith('/api/ppr/persons/') and path.endswith('/photo'))
        if scope['type'] != 'http' or scope.get('method') != 'POST' or not guarded:
            await self.app(scope, receive, send)
            return
        maximum = MAX_BYTES + 65536  # Multipart metadata; file bytes have their own tighter check.
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > maximum:
                body = 'Максимальный размер запроса превышен.'.encode('utf-8')
                await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'text/plain; charset=utf-8'),(b'cache-control',b'no-store')]})
                await send({'type':'http.response.body','body':body})
                return
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)
        async def replay():
            message = next(iterator, None)
            return message if message is not None else await receive()
        await self.app(scope, replay, send)
