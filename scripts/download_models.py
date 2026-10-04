import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse,hashlib,json,re,shutil,tempfile,os
from scripts.common import ROOT,ScriptError,report,run_cli

MODELS={'qwen3-awq':'Qwen/Qwen3-32B-AWQ','bge-m3':'BAAI/bge-m3','bge-reranker':'BAAI/bge-reranker-v2-m3'}
EXTENSIONS={'.safetensors','.bin','.pt','.json','.model','.txt','.md'}
def plan(model,revision,output=None):
    if model not in MODELS:raise ScriptError('Unsupported model alias')
    if not re.fullmatch(r'[0-9a-f]{40}',revision):raise ScriptError('Provide a full 40-character lowercase Hub commit SHA')
    path=Path(output or ROOT/'models'/model).resolve()
    return {'mode':'dry-run','model':model,'repo_id':MODELS[model],'revision':revision,'output':str(path),'network_used':False,'runtime_root_files_only':True}

def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):value.update(block)
    return value.hexdigest()

def download(model,revision,output=None,api=None,snapshot=None):
    info=plan(model,revision,output);destination=Path(info['output'])
    if destination.exists():raise ScriptError('Model output already exists; choose a new directory')
    if api is None or snapshot is None:
        from huggingface_hub import HfApi,snapshot_download
        api=api or HfApi();snapshot=snapshot or snapshot_download
    metadata=api.model_info(info['repo_id'],revision=revision,files_metadata=True)
    if metadata.sha!=revision:raise ScriptError('Hub revision does not match requested commit')
    entries=[entry for entry in metadata.siblings if '/' not in entry.rfilename and '\\' not in entry.rfilename and entry.rfilename!='campus_download_manifest.json' and (Path(entry.rfilename).suffix in EXTENSIONS or entry.rfilename in {'LICENSE','NOTICE'})]
    names={entry.rfilename for entry in entries}
    if not {'config.json','tokenizer_config.json'}<=names or not any(name.endswith(('.safetensors','.bin')) for name in names):raise ScriptError('Required config/tokenizer/weight root files missing')
    if any(entry.size is None for entry in entries):raise ScriptError('Hub did not supply file sizes')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<sum(entry.size for entry in entries)+100*1024*1024:raise ScriptError('Insufficient disk for selected model files')
    stage=Path(tempfile.mkdtemp(prefix='.'+model+'-partial-',dir=destination.parent))
    try:
        snapshot(repo_id=info['repo_id'],revision=revision,local_dir=str(stage),allow_patterns=sorted(names),max_workers=2)
        files=[]
        for entry in entries:
            path=(stage/entry.rfilename).resolve()
            if not path.is_relative_to(stage) or not path.is_file() or path.stat().st_size!=entry.size:raise ScriptError('Downloaded file missing, unsafe or size mismatch')
            sha=digest(path);lfs=entry.lfs
            reference=lfs.get('sha256') if isinstance(lfs,dict) else getattr(lfs,'sha256',None)
            if reference and sha!=reference:raise ScriptError('Downloaded file hash differs from Hub LFS metadata')
            files.append({'name':entry.rfilename,'size':entry.size,'sha256':sha,'hub_lfs_hash_checked':bool(reference)})
        if model=='qwen3-awq':
            from deployment.vllm.check_model import check
            check(stage)
        record={'repo_id':info['repo_id'],'revision':revision,'model_alias':model,'files':sorted(files,key=lambda row:row['name']),'tensor_contents_validated':False}
        (stage/'campus_download_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
        if destination.exists():raise ScriptError('Model output appeared during download; refused to overwrite')
        stage.rename(destination)
        return {'mode':'apply','model':model,'revision':revision,'output':str(destination),'files':len(files),'network_used':True,'hashes_recorded':True,'tensor_contents_validated':False}
    finally:
        if stage.exists():shutil.rmtree(stage)

def main():
    p=argparse.ArgumentParser(description='Pinned model downloads; no network unless --apply; no remote Python code execution')
    p.add_argument('--model',choices=list(MODELS),required=True);p.add_argument('--revision',required=True);p.add_argument('--output',type=Path);p.add_argument('--apply',action='store_true')
    a=p.parse_args();report(download(a.model,a.revision,a.output) if a.apply else plan(a.model,a.revision,a.output))
if __name__=='__main__':raise SystemExit(run_cli(main))
