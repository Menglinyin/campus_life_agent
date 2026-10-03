import httpx
from fastapi import APIRouter,Depends,Request,UploadFile,File,HTTPException,Response
from app.core.auth import current_user
from app.schemas.voice import SpeechRequest
from app.core.errors import ServiceError
router=APIRouter()
@router.post('/voice/transcribe')
async def transcribe(request:Request,audio:UploadFile=File(...),user=Depends(current_user)):
    url=request.app.state.services.settings.asr_url
    if not url: raise HTTPException(503,'ASR service not configured')
    content=bytearray()
    while chunk:=await audio.read(65536):
        content.extend(chunk)
        if len(content)>8*1024*1024: raise HTTPException(413,'Audio exceeds 8 MiB')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result=await client.post(url,files={'audio':('audio',bytes(content),audio.content_type or 'application/octet-stream')})
            result.raise_for_status(); text=result.json()['text']
            if not isinstance(text,str) or len(text)>10000: raise ValueError('Invalid ASR response')
            return {'text':text}
    except (httpx.HTTPError,KeyError,ValueError) as exc: raise ServiceError('ASR unavailable') from exc
@router.post('/voice/synthesize')
async def synthesize(body:SpeechRequest,request:Request,user=Depends(current_user)):
    s=request.app.state.services; message=s.conversations.assistant_message(user,str(body.message_id))
    if not s.settings.tts_url: raise HTTPException(503,'TTS service not configured')
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            result=await client.post(s.settings.tts_url,json={'text':message['content'][:1000],'voice':'default'})
            result.raise_for_status()
            if not result.content.startswith(b'RIFF') or len(result.content)>16*1024*1024: raise ValueError('Invalid WAV')
            return Response(result.content,media_type='audio/wav')
    except (httpx.HTTPError,ValueError) as exc: raise ServiceError('TTS unavailable') from exc
