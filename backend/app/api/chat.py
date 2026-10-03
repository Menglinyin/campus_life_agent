import asyncio
from fastapi import APIRouter,Depends,Request
from app.core.auth import current_user
from app.schemas.chat import ChatRequest,ChatResponse
from app.memory.preference_extractor import extract_preferences
router=APIRouter()
@router.post('/chat',response_model=ChatResponse)
async def chat(body:ChatRequest,request:Request,user=Depends(current_user)):
    s=request.app.state.services
    sid=s.conversations.ensure(user,str(body.session_id) if body.session_id else None)
    async with s.locks[sid]:
        snapshot=s.memory.get(user,sid)
        updates=extract_preferences(body.message)
        if updates: s.preferences.update(user,updates)
        slots=dict(snapshot['slots'])
        if body.date: slots['date']=body.date.isoformat()
        async with asyncio.timeout(s.settings.model_timeout*s.settings.max_tool_steps+30):
            result=await s.graph.ainvoke({'user':user,'text':body.message,'history':snapshot['messages'],'slots':slots,'preferences':s.preferences.get(user)},config={'recursion_limit':30})
        payload={'results':result['results']}
        mid=s.conversations.save_turn(user,sid,body.message,result['answer'],payload,result['slots'],snapshot['version'])
        s.memory.invalidate(user,sid)
        return ChatResponse(session_id=sid,message_id=mid,answer=result['answer'],results=result['results'],mode='vllm' if s.settings.llm_base_url else 'demo')
