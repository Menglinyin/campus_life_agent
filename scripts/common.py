import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(BACKEND) not in sys.path:sys.path.insert(0,str(BACKEND))

class ScriptError(RuntimeError):pass

def load_settings(profile='demo',env_file=None):
    from config.loader import load_settings as load
    from sqlalchemy.engine import make_url
    settings=load(profile,env_file)
    url=make_url(settings.database_url)
    if url.drivername.startswith('sqlite') and url.database and url.database!=':memory:' and not Path(url.database).is_absolute():
        settings.database_url=url.set(database=str((BACKEND/url.database).resolve())).render_as_string(hide_password=False)
    if settings.chroma_path and not Path(settings.chroma_path).is_absolute():settings.chroma_path=str((BACKEND/settings.chroma_path).resolve())
    return settings

def config_args(parser):
    parser.add_argument('--profile',choices=['demo','production'],default='demo')
    parser.add_argument('--env-file',type=Path)

def check_database(settings):
    from migrations.manage import execute
    from sqlalchemy.engine import make_url
    return execute('check',make_url(settings.database_url))

def check_owner(owner):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@-]{0,63}',owner):raise ScriptError('Invalid owner ID')
    return owner

def read_text(path):
    from app.rag.collectors.documents import read_document
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=2*1024*1024:raise ScriptError('Use a non-empty UTF-8 TXT/MD file no larger than 2MiB')
    value=read_document(path)
    if not value.strip():raise ScriptError('Document is empty')
    return value

def report(value,output=None):
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if output:
        path=Path(output)
        if path.exists():raise ScriptError('Output exists; choose a new output file')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as stream:stream.write(text)
    else:print(text,end='')
    return value

def run_cli(main):
    try:return main() or 0
    except ScriptError as error:print(str(error),file=sys.stderr);return 2
    except Exception:
        print('Script failed; check configuration, dependencies and inputs. Credentials/data/error bodies omitted.',file=sys.stderr)
        return 2
