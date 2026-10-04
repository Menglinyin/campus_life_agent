import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse,importlib.metadata,platform,shutil,subprocess
from scripts.common import ROOT,run_cli,report,load_settings,config_args

BASE={'fastapi':'0.115.9','uvicorn':'0.34.2','SQLAlchemy':'2.0.40','PyMySQL':'1.1.1','pydantic-settings':'2.9.1','httpx':'0.28.1','langgraph':'0.4.3','redis':'5.2.1','numpy':'2.2.5','jieba':'0.42.1','rank-bm25':'0.2.2','jsonschema':'4.23.0','python-multipart':'0.0.20','pyecharts':'2.0.8','mcp':'1.9.4','PyYAML':'6.0.3','alembic':'1.16.5'}

def inspect_environment(with_config=False,profile='demo',env_file=None,gpu=False):
    dependencies={};missing=[];mismatched=[]
    for name,pin in BASE.items():
        try:version=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:version=None;missing.append(name)
        if version and version!=pin:mismatched.append(name)
        dependencies[name]={'expected':pin,'installed':version}
    folders=['backend','config','data','migrations','mcp_servers','frontend']
    missing_folders=[name for name in folders if not (ROOT/name).is_dir()]
    result={'python':platform.python_version(),'supported_python':sys.version_info[:2] in [(3,11),(3,12)],'dependencies':dependencies,'missing_dependencies':missing,'version_mismatches':mismatched,'missing_folders':missing_folders,'config':'not_checked','gpu':'not_probed','network_probed':False,'database_connected':False,'models_loaded':False}
    if with_config:
        load_settings(profile,env_file);result['config']='valid'
    if gpu:
        program=shutil.which('nvidia-smi')
        if not program:result['gpu']={'available':False,'reason':'nvidia-smi unavailable'}
        else:
            completed=subprocess.run([program,'--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
            result['gpu']={'available':completed.returncode==0,'devices':completed.stdout.strip().splitlines() if completed.returncode==0 else []}
    result['ok']=result['supported_python'] and not missing and not mismatched and not missing_folders
    return result

def main():
    p=argparse.ArgumentParser(description='Read-only local dependency check; no DB/model/network initialization')
    config_args(p);p.add_argument('--config',action='store_true');p.add_argument('--gpu',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();result=inspect_environment(a.config,a.profile,a.env_file,a.gpu);report(result,a.output)
    return 0 if result['ok'] else 2
if __name__=='__main__':raise SystemExit(run_cli(main))
