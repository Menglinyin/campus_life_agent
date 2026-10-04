import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse
from scripts.common import ROOT,load_settings,check_database,report,run_cli,ScriptError

def import_business(manifest=None,business_dir=None,env_file=None,apply=False):
    from data.validate import read_manifest
    manifest=Path(manifest or ROOT/'data/manifests/sources.yaml')
    batches,_=read_manifest(manifest,business_dir=business_dir)
    result={'mode':'apply' if apply else 'dry-run','business_rows':{kind:len(rows) for kind,rows in batches.items()},'knowledge_imported':False}
    if apply:
        from data.import_data import apply_batches
        settings=load_settings('demo',env_file)
        if not settings.demo:raise ScriptError('Synthetic business data may only be imported in demo mode')
        check_database(settings)
        apply_batches(settings,batches,[])
    return result

def main():
    p=argparse.ArgumentParser(description='Validate/import the data module synthetic CSVs; no knowledge side effects')
    p.add_argument('--manifest',type=Path);p.add_argument('--business-dir',type=Path);p.add_argument('--env-file',type=Path);p.add_argument('--apply',action='store_true')
    a=p.parse_args();report(import_business(a.manifest,a.business_dir,a.env_file,a.apply))
if __name__=='__main__':raise SystemExit(run_cli(main))
