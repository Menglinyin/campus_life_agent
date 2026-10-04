import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse,yaml
from scripts.common import ROOT,load_settings,report,run_cli,config_args,ScriptError

PUBLIC_FIELDS=['demo','session_ttl','history_turns','embedding_backend','embedding_model','embedding_fp16','embedding_max_tokens','chunk_tokens','chunk_overlap','retrieval_k','llm_model','max_tool_steps','model_timeout','tool_timeout']
CONSTANT_FIELDS={
 'rag.yaml':['embedding_dimension','embedding_batch_size','bm25_tokenizer','dense_candidate_k','bm25_candidate_k','rrf_k'],
 'inference.yaml':['temperature','max_output_tokens','enable_thinking','max_tools_per_step','recursion_limit']}

def parameters(profile='demo',env_file=None):
    settings=load_settings(profile,env_file)
    constants={}
    for filename,names in CONSTANT_FIELDS.items():
        document=yaml.safe_load((ROOT/'config'/filename).read_text())
        supplied=document.get('implementation_constants',{})
        selected={}
        for name in names:
            if name not in supplied:continue
            value=supplied[name]
            expected=bool if name=='enable_thinking' else str if name=='bm25_tokenizer' else (int,float) if name=='temperature' else int
            if not isinstance(value,expected) or isinstance(value,bool) and expected is not bool:
                raise ScriptError('Invalid implementation constant type; export refused')
            selected[name]=value
        constants[filename]=selected
    return {'profile':profile,'settings':{field:('[URL omitted]' if isinstance(getattr(settings,field),str) and '://' in getattr(settings,field) else getattr(settings,field)) for field in PUBLIC_FIELDS},'configured':{'redis':bool(settings.redis_url),'chroma':bool(settings.chroma_path),'llm':bool(settings.llm_base_url),'reranker':bool(settings.reranker_model),'asr':bool(settings.asr_url),'tts':bool(settings.tts_url)},'mcp_tool_count':len(settings.mcp_servers),'implementation_constants_reference':constants,'reference_values_are_measured_performance':False,'credentials_exported':False}

def main():
    p=argparse.ArgumentParser(description='Export allowlisted operational parameters, never raw Settings or secrets')
    config_args(p);p.add_argument('--output',type=Path)
    a=p.parse_args();report(parameters(a.profile,a.env_file),a.output)
if __name__=='__main__':raise SystemExit(run_cli(main))
