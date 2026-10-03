import httpx
from app.core.errors import ServiceError
class ModelClient:
    def __init__(self,settings):
        self.settings=settings
        self.http=httpx.AsyncClient(timeout=settings.model_timeout)
    async def chat(self,messages,tools):
        try:
            response=await self.http.post(self.settings.llm_base_url.rstrip("/")+"/chat/completions",headers={"Authorization":"Bearer "+self.settings.llm_api_key},json={"model":self.settings.llm_model,"messages":messages,"tools":tools,"tool_choice":"auto","temperature":0.2,"max_tokens":768,"chat_template_kwargs":{"enable_thinking":False}})
            response.raise_for_status(); return response.json()["choices"][0]["message"]
        except (httpx.HTTPError,KeyError,ValueError) as exc: raise ServiceError("Model unavailable") from exc
    async def close(self): await self.http.aclose()
