from fastapi import APIRouter,Depends,Request
from app.core.auth import current_user
from app.schemas.charts import ChartRequest
from app.services.visualization import chart_options
router=APIRouter()
@router.post('/charts')
def charts(body:ChartRequest,request:Request,user=Depends(current_user)):
    message=request.app.state.services.conversations.assistant_message(user,str(body.message_id))
    return {'options':chart_options(message['payload']['results'])}
