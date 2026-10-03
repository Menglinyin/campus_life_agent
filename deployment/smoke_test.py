import argparse,json,os
import urllib.request,urllib.error

def request(url,body=None,token=None):
    headers={}
    if token:headers['Authorization']='Bearer '+token
    if body is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=330) as response:return json.loads(response.read())
def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:8080');p.add_argument('--mode',choices=['demo','production'],default='demo');a=p.parse_args()
    token=os.environ.get('CAMPUS_TEST_TOKEN','demo-token' if a.mode=='demo' else '')
    if not token:p.error('Set CAMPUS_TEST_TOKEN for production smoke test')
    base=a.base_url.rstrip('/')
    try:
        assert request(base+'/api/health')['status']=='ok'
        r=request(base+'/api/chat',{'message':'今天查询空闲教室'},token)
        assert r['session_id'] and r['message_id'] and isinstance(r['results'],list)
    except (urllib.error.URLError,ValueError,KeyError,AssertionError):p.error('Smoke test failed; inspect container health and logs')
    print('Health and authenticated chat requests passed; this is not a load test.')
if __name__=='__main__':main()
