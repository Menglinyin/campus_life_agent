"""Run: python config/launch.py --check, or python config/launch.py."""
import argparse
from pathlib import Path
import os
import subprocess
import signal
import sys
if __package__:
    from .loader import BACKEND_ROOT, ConfigError, load_settings, settings_environment
else:
    from loader import BACKEND_ROOT, ConfigError, load_settings, settings_environment

def main():
    parser=argparse.ArgumentParser(description='Validate and launch campus backend from YAML')
    parser.add_argument('--profile',choices=['demo','production'],default='demo')
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    try:
        if not 1<=args.port<=65535: raise ConfigError('Port must be between 1 and 65535')
        settings=load_settings(args.profile,args.env_file)
    except ConfigError as exc:
        print(str(exc),file=sys.stderr); return 2
    print(f'Configuration valid: {args.profile}',flush=True)
    if args.check: return 0
    child_env={**os.environ,**settings_environment(settings)}
    # Use existing uvicorn/backend; do not create a second Agent implementation.
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host',args.host,'--port',str(args.port),'--workers','1'],cwd=BACKEND_ROOT,env=child_env)
    def stop(signum, frame):
        if process.poll() is None: process.terminate()
    previous=signal.signal(signal.SIGTERM,stop)
    try: return process.wait()
    except KeyboardInterrupt:
        if process.poll() is None: process.terminate()
        try: return process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill();return process.wait()
    finally:
        signal.signal(signal.SIGTERM,previous)
if __name__=='__main__': raise SystemExit(main())
