import argparse
from pathlib import Path
import sys
import uvicorn
from .common.config import ServerSettings
from .common.server import create_app

PORTS={'query':8100,'recommendation':8101,'feedback':8102}
def main(default_kind=None,default_port=None):
    parser=argparse.ArgumentParser(description='Campus MCP Streamable HTTP services')
    if default_kind is None:parser.add_argument('kind',choices=list(PORTS))
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=default_port)
    parser.add_argument('--env-file',type=Path)
    args=parser.parse_args();kind=default_kind or args.kind;port=args.port if args.port is not None else PORTS[kind]
    if not 1<=port<=65535:parser.error('Port must be between 1 and 65535')
    if args.env_file and not args.env_file.is_file():parser.error('Env file not found')
    try:
        settings=ServerSettings(**({'_env_file':args.env_file} if args.env_file else {})).require_token()
        app=create_app(kind,settings)
    except Exception:
        print('Invalid MCP configuration; check token, users, database and dependency setup. Values omitted.',file=sys.stderr)
        return 2
    uvicorn.run(app,host=args.host,port=port,workers=1,access_log=False,log_level='warning',timeout_keep_alive=5)
    return 0
if __name__=='__main__':raise SystemExit(main())
