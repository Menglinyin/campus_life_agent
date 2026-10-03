"""Create private deployment files; refuses to overwrite existing credentials."""
import argparse,json,secrets,os
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent

def initialize(root,mode):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if mode not in {'demo','production'}:raise ValueError('Invalid mode')
    paths=[root/'.env']
    if mode=='production':paths+=[root/'secrets'/name for name in ['mysql_password.txt','mysql_root_password.txt','redis_password.txt']]
    if any(p.exists() for p in paths):raise ValueError('Private files already exist; refusing to overwrite')
    values={'HTTP_PORT':'8080'};payloads={}
    if mode=='production':
        mysql,admin,redis,api,user=[secrets.token_urlsafe(32) for _ in range(5)]
        values.update(MYSQL_PASSWORD_URLENCODED=quote(mysql,safe=''),REDIS_PASSWORD_URLENCODED=quote(redis,safe=''),VLLM_API_KEY=api,CAMPUS_USER_TOKENS=json.dumps({user:'student-001'},separators=(',',':')),CAMPUS_LLM_BASE_URL='http://vllm:8000/v1',CAMPUS_MCP_SERVERS='{}',CAMPUS_MCP_TOKEN='',CAMPUS_ASR_URL='',CAMPUS_TTS_URL='',MODEL_DIR='/ABSOLUTE/PATH/TO/Qwen3-32B-AWQ',GPU_DEVICE_0='0',GPU_DEVICE_1='1',VLLM_MAX_MODEL_LEN='8192',VLLM_MAX_NUM_SEQS='4',VLLM_GPU_MEMORY_UTILIZATION='0.90')
        payloads={root/'secrets/mysql_password.txt':mysql,root/'secrets/mysql_root_password.txt':admin,root/'secrets/redis_password.txt':redis}
    # Single quotes protect JSON and literal values from Compose env interpolation.
    payloads[root/'.env']=''.join(f"{k}='{v}'\n" for k,v in values.items())
    for p in payloads:p.parent.mkdir(parents=True,exist_ok=True)
    for p,text in payloads.items():
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text+'\n' if not text.endswith('\n') else text)
    return paths

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['demo','production'],default='demo');a=p.parse_args()
    try:initialize(ROOT,a.mode)
    except (ValueError,OSError) as exc:p.error(str(exc))
    print('Created private deployment files. Edit .env locally; credentials are not printed.')
if __name__=='__main__':main()
