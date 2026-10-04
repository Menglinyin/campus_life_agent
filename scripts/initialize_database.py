import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse
from scripts.common import run_cli,report,ScriptError

def initialize(env_file=None,action='upgrade',apply=False):
    from migrations.config import database_url
    from migrations.manage import execute
    url=database_url(env_file)
    if not apply:
        exists=Path(url.database).is_file() if url.drivername.startswith('sqlite') else None
        return {'mode':'dry-run','action':action,'sqlite_file_exists':exists,'connected':False,'note':'Preview only; structure preflight happens on --apply'}
    return {'mode':'apply',**execute(action,url)}
def main():
    p=argparse.ArgumentParser(description='Use existing Alembic migrations; dry-run by default')
    p.add_argument('--env-file',type=Path);p.add_argument('--action',choices=['upgrade','adopt-existing'],default='upgrade');p.add_argument('--apply',action='store_true')
    a=p.parse_args();report(initialize(a.env_file,a.action,a.apply))
if __name__=='__main__':raise SystemExit(run_cli(main))
