"""Pure ASGI middleware: service authentication on every stateless request."""
from contextvars import ContextVar
import hmac
import json
from urllib.parse import urlsplit

_USER=ContextVar('campus_mcp_user',default=None)
def current_user():
    user=_USER.get()
    if user is None: raise RuntimeError('Authenticated request context required')
    return user

class ServiceAuth:
    def __init__(self, app, settings):
        self.app=app;self.settings=settings;settings.require_token()
    async def reply(self, send, status, detail):
        body=json.dumps({'detail':detail}).encode()
        headers=[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode()),(b'cache-control',b'no-store')]
        if status==401: headers.append((b'www-authenticate',b'Bearer realm="campus-mcp"'))
        await send({'type':'http.response.start','status':status,'headers':headers})
        await send({'type':'http.response.body','body':body})
    async def __call__(self, scope, receive, send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        values={}
        for key,value in scope.get('headers',[]):values.setdefault(key.lower(),[]).append(value.decode('latin-1'))
        def one(key):
            found=values.get(key,[])
            return found[0] if len(found)==1 else None
        host=one(b'host')
        try: hostname=urlsplit('//'+(host or '')).hostname
        except ValueError: hostname=None
        if hostname not in self.settings.mcp_allowed_hosts:
            return await self.reply(send,403,'Host refused')
        origin=one(b'origin')
        if b'origin' in values and (origin is None or origin not in self.settings.mcp_allowed_origins):
            return await self.reply(send,403,'Origin refused')
        # Health is liveness only, with no user data or dependency details.
        if scope['path']=='/health' and scope['method']=='GET':
            return await self.app(scope,receive,send)
        if scope['path'].rstrip('/')!='/mcp':return await self.reply(send,404,'Not found')
        auth=one(b'authorization') or ''
        expected='Bearer '+self.settings.mcp_token.get_secret_value()
        if not hmac.compare_digest(auth.encode('latin-1'),expected.encode('ascii')):
            return await self.reply(send,401,'Service authentication required')
        user=one(b'x-campus-user')
        if user not in self.settings.mcp_allowed_users:
            return await self.reply(send,403,'User refused')
        if scope['method']=='POST':
            try: length=int(one(b'content-length')) if b'content-length' in values else None
            except (ValueError,TypeError):return await self.reply(send,400,'Invalid length')
            cap=self.settings.mcp_max_body_bytes
            if length is not None and not 0<=length<=cap:return await self.reply(send,413,'Request too large')
            body=bytearray()
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                body.extend(message.get('body',b''))
                if len(body)>cap:return await self.reply(send,413,'Request too large')
                if not message.get('more_body',False):break
            if length is not None and len(body)!=length:return await self.reply(send,400,'Invalid length')
            delivered=False
            original_receive=receive
            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {'type':'http.request','body':bytes(body),'more_body':False}
                return await original_receive()
            receive=buffered_receive
        marker=_USER.set(user)
        try:return await self.app(scope,receive,send)
        finally:_USER.reset(marker)
