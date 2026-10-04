"""Read-only demonstration; token from environment, not a CLI argument."""
import argparse,asyncio,json,os
from datetime import datetime
from zoneinfo import ZoneInfo
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def run(args):
    token=os.environ.get('CAMPUS_MCP_TOKEN','')
    if not token:raise RuntimeError('Set CAMPUS_MCP_TOKEN in this terminal')
    async with asyncio.timeout(20):
        async with streamablehttp_client(args.url,headers={'Authorization':'Bearer '+token,'X-Campus-User':args.user}) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                discovered=await session.list_tools()
                print('Available tools:',', '.join(t.name for t in discovered.tools))
                result=await session.call_tool(args.tool,arguments=json.loads(args.arguments))
                if result.isError:raise RuntimeError('Tool returned error')
                print(''.join(block.text for block in result.content if block.type=='text'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8100/mcp');p.add_argument('--user',default='demo-student')
    p.add_argument('--tool',choices=['query_classrooms','query_courses','query_dishes','query_secondhand','search_knowledge','recommend_dishes','recommend_courses','list_my_reviews'],default='query_classrooms')
    p.add_argument('--arguments',default=json.dumps({'date':datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()}))
    args=p.parse_args()
    try:asyncio.run(run(args))
    except Exception:raise SystemExit('MCP request failed; check service, token, user and arguments.')
if __name__=='__main__':main()
