"""Run from project root: python -m mcp_servers.query.server"""
from mcp_servers.launch import main
if __name__=='__main__':raise SystemExit(main(default_kind='query',default_port=8100))
