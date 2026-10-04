from mcp_servers.common import backend  # noqa: F401
from app.services.recommendations import recommend_dishes

def run(runtime,args,user):
    if args.date is None:return {'needs_date':True,'rows':[]}
    preferences=runtime.preferences.get(user)
    preferences={k:v for k,v in preferences.items() if k in {'budget','spice','vegetarian'}}
    # Revalidate SQL preference values through the same backend contract.
    from app.schemas.tools import ToolArgs
    preferences=ToolArgs.model_validate(preferences).model_dump(include={'budget','spice','vegetarian'},exclude_none=True)
    explicit=args.model_dump(include={'budget','spice','vegetarian'},exclude_none=True)
    rows=runtime.rows('dishes',args.date.isoformat())
    return {'rows':recommend_dishes(rows,{**preferences,**explicit})}
