from datetime import datetime,timezone
from pathlib import Path
import os,sys,json,subprocess
import pytest
from sqlalchemy import inspect,select,text
from sqlalchemy.engine import make_url
from alembic import command
from migrations.config import MigrationError,alembic_config,database_url,make_engine
from migrations.manage import execute
from migrations.checks import schema_issues
from migrations.backend_metadata import metadata,PROJECT
from app.storage.mysql import Database
from app.storage.models import User,Conversation,Message,Preference,Feedback,KnowledgeChunk,Dish

@pytest.fixture
def url(tmp_path):return make_url('sqlite:///'+(tmp_path/'campus.db').as_posix())

def seed(url):
    db=Database(url.render_as_string(hide_password=False))
    try:
        with db.transaction() as s:
            s.add(User(id='student-a'));s.flush()
            s.add(Conversation(id='session-a',user_id='student-a',slots={'date':'2026-10-04'}));s.flush()
            s.add(Message(id='message-a',session_id='session-a',role='assistant',content='合成回答',payload={'results':[]}))
            s.add(Preference(user_id='student-a',values={'budget':10,'spice':0}))
    finally:db.close()

def test_empty_upgrade_matches_all_backend_tables(url):
    result=execute('upgrade',url)
    assert result['revisions']==['0004'] and set(result['tables'])==set(metadata.tables)
    assert len(result['tables'])==11
    assert execute('check',url)=={'schema_matches':True,'revision':'0004'}
    engine=make_engine(url)
    with engine.connect() as c:
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
        assert not schema_issues(c)
        assert inspect(c).get_indexes('knowledge_chunks')[0]['name']=='ix_knowledge_chunks_owner'
        assert inspect(c).get_columns('chat_sessions')[2]['default'] is None
    engine.dispose()

def test_phased_upgrade_preserves_history_preferences_and_json(url):
    assert len(execute('upgrade',url,target='0001')['tables'])==4
    seed(url)
    assert len(execute('upgrade',url,target='0002')['tables'])==8
    assert len(execute('upgrade',url,target='0003')['tables'])==10
    execute('upgrade',url)
    db=Database(url.render_as_string(hide_password=False))
    with db.transaction() as s:
        assert s.get(Message,'message-a').content=='合成回答'
        assert s.get(Preference,'student-a').values=={'budget':10,'spice':0}
        assert s.get(Conversation,'session-a').slots=={'date':'2026-10-04'}
    db.close()

def test_repeated_upgrade_is_noop(url):
    execute('upgrade',url);seed(url)
    first=execute('current',url);execute('upgrade',url);execute('upgrade',url)
    assert execute('current',url)==first
    db=Database(url.render_as_string(hide_password=False))
    with db.transaction() as s:assert s.get(Message,'message-a').content=='合成回答'
    db.close()

def test_adopt_create_all_database_preserves_all_payloads(url):
    db=Database(url.render_as_string(hide_password=False));db.initialize();db.close();seed(url)
    db=Database(url.render_as_string(hide_password=False))
    with db.transaction() as s:
        s.add(KnowledgeChunk(id='chunk-a',owner='student-a',source='测试来源',text='合成私有笔记'))
        s.add(Feedback(id='review-a',payload={'user_id':'student-a','rating':5,'comment':'合成评价'}))
    db.close()
    assert execute('adopt-existing',url)=={'adopted_revision':'0004','business_data_changed':False}
    assert execute('check',url)['schema_matches']
    execute('upgrade',url)
    db=Database(url.render_as_string(hide_password=False))
    with db.transaction() as s:
        assert s.get(Message,'message-a').content=='合成回答'
        assert s.get(Preference,'student-a').values['spice']==0
        assert s.get(Feedback,'review-a').payload['comment']=='合成评价'
        assert s.get(KnowledgeChunk,'chunk-a').text=='合成私有笔记'
    db.close()
    with pytest.raises(MigrationError,match='already has'):execute('adopt-existing',url)

def test_unversioned_partial_database_is_not_silently_stamped(url):
    engine=make_engine(url,allow_create=True)
    with engine.begin() as c:c.exec_driver_sql('CREATE TABLE users (id VARCHAR(64) PRIMARY KEY NOT NULL)')
    engine.dispose()
    for action in ['upgrade','adopt-existing']:
        with pytest.raises(MigrationError):execute(action,url)
    engine=make_engine(url)
    with engine.connect() as c:assert set(inspect(c).get_table_names())=={'users'}
    engine.dispose()

@pytest.mark.parametrize('alter',[
    'DROP INDEX ix_knowledge_chunks_owner',
    'ALTER TABLE dishes ADD COLUMN unexpected VARCHAR(30)',
    'CREATE UNIQUE INDEX unique_dish_payload ON dishes(payload)',
    'CREATE TABLE unexpected_table (id INTEGER)',
])
def test_adoption_rejects_schema_drift(url,alter):
    db=Database(url.render_as_string(hide_password=False));db.initialize();db.close()
    engine=make_engine(url)
    with engine.begin() as c:c.exec_driver_sql(alter)
    engine.dispose()
    with pytest.raises(MigrationError):execute('adopt-existing',url)
    engine=make_engine(url)
    with engine.connect() as c:assert 'alembic_version' not in inspect(c).get_table_names()
    engine.dispose()

def test_adoption_detects_primary_key_changes(url):
    db=Database(url.render_as_string(hide_password=False));db.initialize();db.close()
    engine=make_engine(url)
    with engine.begin() as c:
        c.exec_driver_sql('DROP TABLE feedback')
        c.exec_driver_sql('CREATE TABLE feedback (id VARCHAR(64) NOT NULL, payload JSON NOT NULL)')
    engine.dispose()
    with pytest.raises(MigrationError,match='primary_key:feedback'):execute('adopt-existing',url)

def test_adoption_detects_existing_foreign_key_violation(url):
    db=Database(url.render_as_string(hide_password=False));db.initialize();db.close()
    import sqlite3
    with sqlite3.connect(url.database) as c:
        c.execute('INSERT INTO user_preferences (user_id, "values") VALUES (?,?)',('absent','{}'))
    with pytest.raises(MigrationError,match='foreign_key_data_violation'):execute('adopt-existing',url)

def test_unknown_revision_and_head_drift_refused(url):
    execute('upgrade',url)
    engine=make_engine(url)
    with engine.begin() as c:c.exec_driver_sql('DROP INDEX ix_knowledge_chunks_owner')
    with pytest.raises(MigrationError):execute('check',url)
    with pytest.raises(MigrationError):execute('upgrade',url)
    with engine.begin() as c:c.exec_driver_sql("UPDATE alembic_version SET version_num='unknown' ")
    engine.dispose()
    with pytest.raises(MigrationError,match='not in'):execute('current',url)

def test_downgrade_guard_and_disposable_reversible_chain(url):
    execute('upgrade',url);seed(url)
    with pytest.raises(MigrationError,match='allow-data-loss'):execute('downgrade',url,target='base')
    assert execute('check',url)['schema_matches']
    result=execute('downgrade',url,target='0003',allow_data_loss=True)
    assert 'feedback' not in result['tables'] and 'knowledge_chunks' in result['tables']
    result=execute('downgrade',url,target='base',allow_data_loss=True)
    assert result['tables']==[] and result['revisions']==[]
    execute('upgrade',url)
    assert execute('check',url)['schema_matches']

@pytest.mark.parametrize('dialect',['mysql','sqlite'])
def test_offline_sql_uses_real_revisions_without_connection(tmp_path,dialect,monkeypatch):
    import migrations.manage as module
    monkeypatch.setattr(module,'make_engine',lambda *a,**k:pytest.fail('Offline must not connect'))
    file=tmp_path/(dialect+'.sql')
    result=execute('sql',dialect=dialect,output=file)
    sql=file.read_text()
    assert result['connected'] is False
    for name in metadata.tables:assert 'CREATE TABLE '+name+' ' in sql or 'CREATE TABLE '+name+' (' in sql
    assert '0004' in sql and 'INSERT INTO alembic_version' in sql
    assert sql.count('CREATE TABLE ')==12
    with pytest.raises(MigrationError,match='exists'):execute('sql',dialect=dialect,output=file)

def test_url_source_precedence_percent_encoding_and_backend_relative_paths(tmp_path):
    env=tmp_path/'database.env';env.write_text('CAMPUS_DATABASE_URL=sqlite:///./campus.db\n')
    result=database_url(env,environ={})
    assert Path(result.database)==PROJECT/'backend/campus.db'
    override='mysql+pymysql://user:p%25ss%40word@db/campus?charset=utf8mb4'
    result=database_url(env,environ={'CAMPUS_DATABASE_URL':override})
    assert result.password=='p%ss@word'
    for bad in ['postgresql://user:secret@db/name','sqlite:///:memory:','garbage','sqlite:///test.db?mode=ro']:
        with pytest.raises(MigrationError):database_url(env,environ={'CAMPUS_DATABASE_URL':bad})
    with pytest.raises(MigrationError):database_url(tmp_path/'absent.env',environ={})
    with pytest.raises(MigrationError):database_url(environ={})

def test_read_only_commands_do_not_create_missing_sqlite(url):
    for action in ['current','check','adopt-existing']:
        with pytest.raises(MigrationError,match='does not exist'):execute(action,url)
    assert not Path(url.database).exists()

def test_migrated_database_works_with_actual_backend_repositories(url):
    execute('upgrade',url)
    db=Database(url.render_as_string(hide_password=False))
    from app.storage.repositories.conversations import Conversations
    from app.storage.repositories.preferences import Preferences
    repo=Conversations(db);prefs=Preferences(db)
    sid=repo.ensure('student-a',None)
    prefs.update('student-a',{'budget':10,'spice':0})
    snapshot=repo.snapshot('student-a',sid)
    mid=repo.save_turn('student-a',sid,'合成请求','合成回答',{'results':[]},{'date':'2026-10-04'},snapshot['version'])
    assert prefs.get('student-a')['budget']==10
    assert repo.snapshot('student-a',sid)['messages'][-1]['content']=='合成回答'
    assert mid
    db.close()

def test_cli_failure_does_not_echo_database_credentials(tmp_path):
    environment={k:v for k,v in os.environ.items() if not k.startswith('CAMPUS_')}
    environment['CAMPUS_DATABASE_URL']='invalid://user:TOP_SECRET_CREDENTIAL@db/name'
    result=subprocess.run([sys.executable,'-m','migrations.manage','current'],cwd=PROJECT,env=environment,capture_output=True,text=True,timeout=10)
    assert result.returncode==2
    assert 'TOP_SECRET_CREDENTIAL' not in result.stdout+result.stderr

def test_autogenerate_new_revision_template_and_apply_in_isolated_copy(url,tmp_path,monkeypatch):
    import shutil,sqlalchemy as sa
    import migrations.config as config_module
    import migrations.backend_metadata as model_module
    import migrations.checks as check_module
    execute('upgrade',url)
    copied=tmp_path/'isolated-migrations'
    shutil.copytree(config_module.ROOT,copied,ignore=shutil.ignore_patterns('__pycache__','reports'))
    monkeypatch.setattr(config_module,'ROOT',copied)
    changed=sa.MetaData()
    for table in metadata.tables.values():table.to_metadata(changed)
    changed.tables['feedback'].append_column(sa.Column('moderation_state',sa.String(16),nullable=True))
    monkeypatch.setattr(model_module,'metadata',changed);monkeypatch.setattr(check_module,'metadata',changed)
    result=execute('revision',url,message='test add moderation state')
    generated=Path(result['path']).read_text()
    assert 'moderation_state' in generated and "'0004'" in generated and result['applied'] is False
    assert Path(result['path']).is_relative_to(copied)
    execute('upgrade',url)
    assert execute('check',url)['schema_matches']
    engine=make_engine(url)
    with engine.connect() as c:assert 'moderation_state' in {r['name'] for r in inspect(c).get_columns('feedback')}
    engine.dispose()
    execute('downgrade',url,target='0004',allow_data_loss=True)
    engine=make_engine(url)
    with engine.connect() as c:assert 'moderation_state' not in {r['name'] for r in inspect(c).get_columns('feedback')}
    engine.dispose()
