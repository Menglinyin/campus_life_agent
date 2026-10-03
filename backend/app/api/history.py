from uuid import UUID
from fastapi import APIRouter,Depends,Request
from app.core.auth import current_user
router=APIRouter()
@router.get('/sessions/{session_id}/messages')
def history(session_id:UUID,request:Request,user=Depends(current_user)):
    return request.app.state.services.conversations.snapshot(user,str(session_id))
@router.get('/preferences')
def preferences(request:Request,user=Depends(current_user)):
    return request.app.state.services.preferences.get(user)
