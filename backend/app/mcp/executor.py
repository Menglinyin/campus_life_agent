from app.schemas.tools import ToolArgs
from app.services.recommendations import recommend_dishes
from .router import server_for
from .client import MCPClient
from app.agent.result_validation import validate_result
class Executor:
    def __init__(self,settings,campus,rag): self.settings=settings; self.campus=campus; self.rag=rag; self.client=MCPClient(settings)
    async def execute(self,name,arguments,user,preferences):
        args=ToolArgs.model_validate(arguments)
        url=server_for(self.settings,name)
        if name in {"query_classrooms","query_courses","recommend_dishes"} and args.date is None:
            return {"needs_date":True,"rows":[]}
        if url:
            result=await self.client.call(url,name,args.model_dump(mode="json",exclude_none=True,exclude_defaults=True),user)
            return validate_result(result)
        date=args.date.isoformat() if args.date else None
        if name=="search_knowledge": return {"rows":self.rag.search(args.query,user)}
        kind={"query_classrooms":"classrooms","query_courses":"courses","recommend_dishes":"dishes","query_secondhand":"secondhand"}[name]
        rows=self.campus.list(kind,date)
        if kind=="classrooms": rows=[r for r in rows if r.get("available")]
        if kind=="courses": rows=[r for r in rows if r.get("auditing_allowed",False)]
        if kind=="secondhand": rows=[r for r in rows if r.get("status")=="active" and (not args.query or args.query in r["name"])]
        if kind=="dishes": rows=recommend_dishes(rows,{**preferences,**args.model_dump(exclude_none=True)})
        return {"rows":rows[:20]}
