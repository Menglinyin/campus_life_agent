"""Generate matching local demo fragments without overwriting existing files."""
import argparse,json,os,secrets
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
def generate(output_dir,database_path=None):
    directory=Path(output_dir).resolve()
    path=Path(database_path or PROJECT/'backend/campus.db').resolve()
    files=[directory/'mcp.env',directory/'backend-mcp.env']
    if any(file.exists() for file in files):raise FileExistsError('Choose a new output directory or move existing config files')
    directory.mkdir(parents=True,exist_ok=True)
    token=secrets.token_urlsafe(32)
    database_url='sqlite:///'+path.as_posix()
    mapping={name:'http://127.0.0.1:8100/mcp' for name in ['query_classrooms','query_courses','search_knowledge','query_secondhand']}
    mapping['recommend_dishes']='http://127.0.0.1:8101/mcp'
    shared=f'CAMPUS_DATABASE_URL={database_url}\nCAMPUS_MCP_TOKEN={token}\n'
    contents=[shared+'CAMPUS_MCP_ALLOWED_USERS=["demo-student"]\nCAMPUS_EMBEDDING_BACKEND=demo\nCAMPUS_CHROMA_PATH=\nCAMPUS_RERANKER_MODEL=\n',
              shared+'CAMPUS_DEMO=true\nCAMPUS_USER_TOKENS={"demo-token":"demo-student"}\nCAMPUS_EMBEDDING_BACKEND=demo\nCAMPUS_LLM_BASE_URL=\nCAMPUS_CHROMA_PATH=\nCAMPUS_RERANKER_MODEL=\nCAMPUS_MCP_SERVERS='+json.dumps(mapping,separators=(',',':'))+'\nCAMPUS_TOOL_TIMEOUT=15\nCAMPUS_SESSION_TTL=259200\n']
    for file,text in zip(files,contents):
        fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:out.write(text)
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=PROJECT/'mcp_servers/local')
    parser.add_argument('--database',type=Path)
    args=parser.parse_args()
    try:files=generate(args.output_dir,args.database)
    except OSError:raise SystemExit('Cannot create demo config; check output directory permissions/existing files.')
    print('Created demo config files: '+', '.join(file.name for file in files)+'. Service token omitted.')
if __name__=='__main__':main()
