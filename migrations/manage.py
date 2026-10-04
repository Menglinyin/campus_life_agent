"""Run from project root: python -m migrations.manage --env-file FILE upgrade."""
import argparse,io,json,sys
from pathlib import Path
from alembic import command
from alembic.script import ScriptDirectory
from .config import database_url,make_engine,alembic_config,MigrationError
from .checks import heads,head_revision,tables,schema_issues,preflight_upgrade,adopt_existing,assert_known_revision

def execute(action,url=None,target='head',allow_data_loss=False,output=None,dialect='mysql',message=None):
    if action=='history':
        scripts=ScriptDirectory.from_config(alembic_config())
        return {'head':head_revision(),'history':[{'revision':r.revision,'down_revision':r.down_revision,'description':r.doc} for r in reversed(list(scripts.walk_revisions()))]}
    if action=='sql':
        if not output:raise MigrationError('Provide --output for offline SQL')
        path=Path(output)
        if path.exists():raise MigrationError('Output already exists; choose a new SQL file')
        stream=io.StringIO();cfg=alembic_config(output_buffer=stream);cfg.attributes['offline_dialect']=dialect
        command.upgrade(cfg,target,sql=True)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as file:file.write(stream.getvalue())
        return {'dialect':dialect,'target':target,'output':str(path),'connected':False}
    if url is None:raise MigrationError('Database URL required')
    if action=='downgrade' and not allow_data_loss:
        raise MigrationError('Downgrade drops schema/data; requires --allow-data-loss on a disposable/restorable database')
    if action=='revision' and not message:raise MigrationError('Revision message required')
    engine=make_engine(url,allow_create=action=='upgrade')
    try:
        with engine.begin() as connection:
            cfg=alembic_config(connection)
            if action=='upgrade':
                preflight_upgrade(connection);command.upgrade(cfg,target)
                return {'revisions':list(heads(connection)),'tables':sorted(tables(connection))}
            if action=='adopt-existing':
                revision=adopt_existing(connection);command.stamp(cfg,revision)
                return {'adopted_revision':revision,'business_data_changed':False}
            if action=='downgrade':
                assert_known_revision(connection);command.downgrade(cfg,target)
                return {'revisions':list(heads(connection)),'tables':sorted(tables(connection))}
            if action in {'current','check'}:
                found=assert_known_revision(connection)
                if action=='current':return {'revisions':list(found),'expected_head':head_revision(),'tables':sorted(tables(connection))}
                issues=schema_issues(connection)
                if found!=(head_revision(),):issues.append('revision_not_at_head')
                if issues:raise MigrationError('Database differs from current backend: '+', '.join(issues))
                return {'schema_matches':True,'revision':found[0]}
            if action=='revision':
                if heads(connection)!=(head_revision(),):raise MigrationError('Autogenerate requires database at head')
                script=command.revision(cfg,message=message,autogenerate=True)
                return {'generated_revision':script.revision,'path':script.path,'applied':False}
            raise MigrationError('Unknown migration action')
    finally:engine.dispose()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path)
    actions=parser.add_subparsers(dest='action',required=True)
    for name in ['current','check','adopt-existing','history']:actions.add_parser(name)
    p=actions.add_parser('upgrade');p.add_argument('--to',default='head')
    p=actions.add_parser('downgrade');p.add_argument('--to',required=True);p.add_argument('--allow-data-loss',action='store_true')
    p=actions.add_parser('sql');p.add_argument('--dialect',choices=['mysql','sqlite'],default='mysql');p.add_argument('--to',default='head');p.add_argument('--output',required=True,type=Path)
    p=actions.add_parser('revision');p.add_argument('--message',required=True)
    args=parser.parse_args()
    try:
        url=None if args.action in {'history','sql'} else database_url(args.env_file)
        result=execute(args.action,url=url,target=getattr(args,'to','head'),allow_data_loss=getattr(args,'allow_data_loss',False),output=getattr(args,'output',None),dialect=getattr(args,'dialect','mysql'),message=getattr(args,'message',None))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except MigrationError as error:
        print(str(error),file=sys.stderr);return 2
    except Exception:
        print('Migration failed; connection/SQL/credential details omitted. Inspect database state before retrying.',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
