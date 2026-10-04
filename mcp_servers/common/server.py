from contextlib import asynccontextmanager
import json
from datetime import date as Date
from typing import Annotated, Literal
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse
from .auth import current_user,ServiceAuth
from .schemas import ToolArgs,FeedbackArgs
from .runtime import Runtime

Query=Annotated[str,Field(max_length=1000)]
Budget=Annotated[float,Field(ge=0,le=1000)]
Spice=Annotated[int,Field(ge=0,le=2)]
Target=Literal['classrooms','courses','dishes','secondhand']
TargetID=Annotated[str,Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_.:-]+$')]
Rating=Annotated[int,Field(ge=1,le=5)]
Key=Annotated[str,Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')]
Comment=Annotated[str,Field(max_length=500)]

READ=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)
WRITE=ToolAnnotations(readOnlyHint=False,destructiveHint=False,idempotentHint=True,openWorldHint=False)

def encode(value):return json.dumps(value,ensure_ascii=False,allow_nan=False)

def create_app(kind,settings,runtime=None):
    if kind not in {'query','recommendation','feedback'}:raise ValueError('Unknown server kind')
    settings.require_token()
    resources={}
    @asynccontextmanager
    async def lifecycle(server):
        owned=runtime is None
        resources['runtime']=Runtime(settings,with_rag=kind=='query') if owned else runtime
        try:
            async with sdk_lifecycle(server):yield resources
        finally:
            if owned:resources['runtime'].close()
            resources.clear()
    mcp=FastMCP('campus-'+kind,stateless_http=True,json_response=True)
    def call(handler,args):
        try:return encode(handler(resources['runtime'],args,current_user()))
        except Exception:raise ToolError('Campus tool failed: check arguments, data and access') from None
    def register(name,handler,description):
        async def tool(date: Date|None=None,query: Query='',budget: Budget|None=None,spice: Spice|None=None,vegetarian: bool|None=None)->str:
            try:args=ToolArgs.model_validate({'date':date,'query':query,'budget':budget,'spice':spice,'vegetarian':vegetarian})
            except Exception:raise ToolError('Invalid campus tool arguments') from None
            # Synchronous SQL/RAG is isolated from the server event loop.
            import anyio
            return await anyio.to_thread.run_sync(call,handler,args)
        mcp.tool(name=name,description=description,annotations=READ)(tool)
    if kind=='query':
        from mcp_servers.query import classrooms,courses,dishes,knowledge,secondhand
        for name,handler,description in [
            ('query_classrooms',classrooms.run,'查询指定日期可用教室；缺少日期返回 needs_date。'),
            ('query_courses',courses.run,'查询指定日期允许旁听的课程；旁听仍须征得教师同意。'),
            ('query_dishes',dishes.run,'查询指定日期在售菜品，可按名称关键词过滤；不是个性化推荐。'),
            ('query_secondhand',secondhand.run,'查询在售二手物品，可按名称关键词过滤。'),
            ('search_knowledge',knowledge.run,'检索公共知识和当前已认证用户自己的知识。')]:register(name,handler,description)
    elif kind=='recommendation':
        from mcp_servers.recommendation import dishes,courses
        register('recommend_dishes',dishes.run,'从指定日期在售菜品中按SQL偏好及显式条件筛选，以评分降序/价格升序返回最多10条。')
        register('recommend_courses',courses.run,'筛选允许旁听且匹配关键词的课程，按时间排序；未实现学习兴趣模型。')
    else:
        from mcp_servers.feedback import reviews
        @mcp.tool(description='用户明确确认后提交对校园服务的评价；幂等键在同一次提交重试时复用。',annotations=WRITE)
        async def submit_review(target_kind:Target,target_id:TargetID,rating:Rating,idempotency_key:Key,comment:Comment='')->str:
            try:args=FeedbackArgs.model_validate({'target_kind':target_kind,'target_id':target_id,'rating':rating,'idempotency_key':idempotency_key,'comment':comment})
            except Exception:raise ToolError('Invalid review arguments') from None
            import anyio
            return await anyio.to_thread.run_sync(call,reviews.submit_review,args)
        @mcp.tool(description='仅查询当前已认证用户自己的最多20条评价。',annotations=READ)
        async def list_my_reviews()->str:
            try:
                import anyio
                result=await anyio.to_thread.run_sync(reviews.list_reviews,resources['runtime'],current_user())
                return encode(result)
            except Exception:raise ToolError('Review query failed') from None
    @mcp.custom_route('/health',methods=['GET'])
    async def health(request):return JSONResponse({'status':'ok','server':kind})
    app=mcp.streamable_http_app()
    sdk_lifecycle=app.router.lifespan_context
    app.router.lifespan_context=lifecycle
    return ServiceAuth(app,settings)
