import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from jsonschema import validate
from app.core.errors import ServiceError
class MCPClient:
    def __init__(self,settings): self.settings=settings
    async def call(self,url,name,arguments,user):
        # One scoped connection per call, compatible with pinned MCP SDK v1.
        headers={"X-Campus-User":user}
        if self.settings.mcp_token: headers["Authorization"]="Bearer "+self.settings.mcp_token
        try:
            async with asyncio.timeout(self.settings.tool_timeout):
                async with streamablehttp_client(url,headers=headers) as (read,write,_):
                    async with ClientSession(read,write) as session:
                        await session.initialize()
                        discovered=await session.list_tools()
                        spec=next((t for t in discovered.tools if t.name==name),None)
                        if spec is None: raise ServiceError("Tool unavailable")
                        validate(arguments,spec.inputSchema)
                        result=await session.call_tool(name,arguments=arguments)
                        if result.isError: raise ServiceError("Tool returned error")
                        import json
                        texts=[c.text for c in result.content if c.type=="text"]
                        return json.loads("".join(texts))
        except Exception as exc:
            raise ServiceError("MCP call failed") from exc
