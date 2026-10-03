import asyncio,json,os,socket,subprocess,sys,time
import pytest
from app.settings import Settings
from app.mcp.client import MCPClient

def test_real_mcp_streamable_http(monkeypatch):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    code=f'''
import json
from mcp.server.fastmcp import FastMCP
server=FastMCP('contract-test',host='127.0.0.1',port={port})
@server.tool()
def query_classrooms(date: str):
    return json.dumps({{"rows":[{{"name":"MCP测试教室","date":date,"available":True}}]}})
server.run(transport='streamable-http')
'''
    process=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    monkeypatch.setenv('NO_PROXY','127.0.0.1,localhost')
    try:
        for _ in range(100):
            if process.poll() is not None: pytest.fail('MCP fixture exited before startup')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=0.1): break
            except OSError: time.sleep(0.1)
        else: pytest.fail('MCP fixture startup timed out')
        result=asyncio.run(MCPClient(Settings()).call(f'http://127.0.0.1:{port}/mcp','query_classrooms',{'date':'2026-10-03'},'demo-student'))
        assert result['rows'][0]['name']=='MCP测试教室'
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill();process.wait()
