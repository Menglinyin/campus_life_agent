from contextlib import asynccontextmanager
from uuid import uuid4
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from .errors import VoiceError, BusyError, SizeError
from .runner import InferenceRunner

class BodyLimit:
    """Limit received ASGI bytes as well as Content-Length before multipart parsing."""
    def __init__(self, app, max_bytes):
        self.app = app; self.limit = max_bytes
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        lengths = [v for k, v in scope.get('headers', []) if k.lower() == b'content-length']
        try:
            if len(lengths) > 1: raise SizeError()
            if lengths and (int(lengths[0]) < 0 or int(lengths[0]) > self.limit): raise SizeError()
        except (ValueError, SizeError):
            response = JSONResponse(status_code=413, content={'detail': SizeError.public_message})
            return await response(scope, receive, send)
        # Buffer a bounded body before parser entry, so chunked-limit errors remain 413.
        content = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            chunk = message.get('body', b'')
            if len(content) + len(chunk) > self.limit:
                response = JSONResponse(status_code=413, content={'detail': SizeError.public_message})
                return await response(scope, receive, send)
            content.extend(chunk)
            if not message.get('more_body', False): break
        delivered = False
        async def buffered():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(content), 'more_body': False}
            return await receive()
        return await self.app(scope, buffered, send)

def base_app(kind, settings, engine_factory):
    @asynccontextmanager
    async def lifespan(app):
        # Missing dependencies/weights cause startup failure, not fabricated readiness.
        engine = await asyncio.to_thread(engine_factory)
        app.state.engine = engine
        app.state.runner = InferenceRunner(settings.max_concurrency)
        try: yield
        finally:
            await app.state.runner.close()
            close = getattr(engine, 'close', None)
            if close: await asyncio.to_thread(close)
    app = FastAPI(title='campus-' + kind, lifespan=lifespan)
    app.add_middleware(BodyLimit, max_bytes=settings.max_upload_bytes + 65536 if kind == 'asr' else 16384)
    @app.exception_handler(VoiceError)
    async def failed(request, exc):
        headers = {'Retry-After': '1'} if isinstance(exc, BusyError) else None
        return JSONResponse(status_code=exc.status, content={'detail': exc.public_message}, headers=headers)
    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(status_code=422, content={'detail': '语音请求参数无效。'})
    @app.middleware('http')
    async def identify(request, call_next):
        response = await call_next(request)
        response.headers['X-Request-ID'] = str(uuid4())
        response.headers['Cache-Control'] = 'no-store'
        return response
    @app.get('/health')
    async def health(request: Request):
        return {'status': 'ready', 'service': kind, 'engine': request.app.state.engine.kind}
    return app
