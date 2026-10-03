from contextlib import asynccontextmanager
import logging
from uuid import uuid4
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from app.settings import Settings
from app.bootstrap import Services
from app.core.logging import configure_logging
from app.core.errors import ServiceError
from app.core.request_context import request_id
from app.api import chat,history,charts,voice,health

def create_app(settings=None):
    @asynccontextmanager
    async def lifespan(app):
        configure_logging(); app.state.services=Services(settings or Settings())
        try: yield
        finally: await app.state.services.close()
    app=FastAPI(title='校园生活智能助手',version='0.1.0',lifespan=lifespan)
    @app.middleware('http')
    async def identify(request,call_next):
        rid=str(uuid4()); token=request_id.set(rid)
        try:
            response=await call_next(request); response.headers['X-Request-ID']=rid; return response
        finally: request_id.reset(token)
    @app.exception_handler(ServiceError)
    async def dependency_failure(request,exc):
        logging.getLogger(__name__).error('Dependency failure request=%s',request_id.get())
        return JSONResponse(status_code=503,content={'detail':'服务暂时不可用，请稍后重试。'})
    @app.exception_handler(ValueError)
    async def invalid_operation(request,exc):
        return JSONResponse(status_code=422,content={'detail':'参数或工具结果无效，请检查日期和查询条件。'})
    @app.exception_handler(TimeoutError)
    async def timeout(request,exc):
        return JSONResponse(status_code=504,content={'detail':'请求超时，请稍后重试。'})
    for router in [chat.router,history.router,charts.router,voice.router,health.router]: app.include_router(router,prefix='/api')
    return app
app=create_app()
