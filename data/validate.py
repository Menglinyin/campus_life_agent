import argparse,csv,json,math,re
from datetime import date,time
from pathlib import Path
import yaml
try: from .generate import FIELDS
except ImportError: from generate import FIELDS
DATA_ROOT=Path(__file__).resolve().parent
class DataError(ValueError):pass

def safe_path(root,value):
    if not isinstance(value,str):raise DataError('Manifest path must be a string')
    path=(Path(root)/value).resolve()
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file():raise DataError('Manifest path escapes data root or is missing')
    return path

def boolean(value):
    if value not in {'true','false'}:raise DataError('Boolean must be true or false')
    return value=='true'
def number(value,low,high):
    try:n=float(value)
    except (ValueError,TypeError):raise DataError('Invalid numeric field') from None
    if not math.isfinite(n) or not low<=n<=high:raise DataError('Numeric field is out of range')
    return n

def read_business(path,kind):
    if kind not in FIELDS:raise DataError('Unknown dataset kind')
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=FIELDS[kind]:raise DataError(f'{kind}: CSV columns or order do not match schema')
        result=[];ids=set()
        for line,row in enumerate(reader,2):
            try:
                if None in row or any(v is None or len(v)>1000 for v in row.values()):raise DataError('Invalid CSV row')
                cid=row.pop('id')
                if not re.fullmatch(r'synthetic-[a-zA-Z0-9-]{1,54}',cid) or cid in ids:raise DataError('Invalid or duplicate synthetic ID')
                ids.add(cid)
                if not row['name'].startswith('合成') or len(row['name'])>100:raise DataError('Names must explicitly identify synthetic data')
                if 'date' in row:row['date']=date.fromisoformat(row['date']).isoformat()
                for field in ['available','vegetarian','auditing_allowed']:
                    if field in row:row[field]=boolean(row[field])
                if 'seats' in row:
                    if not row['seats'].isdigit():raise DataError('seats must be integer')
                    row['seats']=int(number(row['seats'],1,1000))
                if 'price' in row:row['price']=number(row['price'],0,10000)
                if 'rating' in row:row['rating']=number(row['rating'],0,5)
                if 'spice' in row:
                    if row['spice'] not in {'0','1','2'}:raise DataError('Invalid spice level')
                    row['spice']=int(row['spice'])
                if 'time' in row:time.fromisoformat(row['time'])
                if 'status' in row and row['status'] not in {'active','sold'}:raise DataError('Invalid item status')
                result.append({'id':cid,'payload':row})
            except (ValueError,KeyError,TypeError) as exc:raise DataError(f'{kind}: invalid row at line {line}: {exc}') from None
    return result

def read_manifest(path,root=DATA_ROOT,business_dir=None):
    try:doc=yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except (OSError,yaml.YAMLError):raise DataError('Cannot read manifest') from None
    if not isinstance(doc,dict) or doc.get('schema_version')!=1 or doc.get('synthetic_only') is not True:raise DataError('Manifest must declare synthetic_only and schema_version 1')
    business=doc.get('business');knowledge=doc.get('knowledge')
    if not isinstance(business,dict) or set(business)!=set(FIELDS) or not isinstance(knowledge,list):raise DataError('Manifest must contain four business sources and a knowledge list')
    batches={}
    for kind,source in business.items():
        if not isinstance(source,dict):raise DataError('Invalid business source')
        path=Path(business_dir)/f'{kind}.csv' if business_dir else safe_path(root,source.get('path'))
        batches[kind]=read_business(path,kind)
    docs=[];seen=set()
    for item in knowledge:
        if not isinstance(item,dict):raise DataError('Invalid knowledge source')
        owner=item.get('owner');source=item.get('source')
        if owner not in {'public','synthetic-student-a','synthetic-student-b'} or not isinstance(source,str) or not source.startswith('合成') or len(source)>255:raise DataError('Invalid synthetic knowledge metadata')
        if (owner,source) in seen:raise DataError('Duplicate knowledge source')
        seen.add((owner,source));path=safe_path(root,item.get('path'))
        text=path.read_text(encoding='utf-8')
        if not text.strip() or len(text)>100000 or '合成' not in text:raise DataError('Invalid synthetic knowledge text')
        docs.append({'source':source,'owner':owner,'text':text})
    return batches,docs

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,default=DATA_ROOT/'manifests/sources.yaml');p.add_argument('--business-dir',type=Path);a=p.parse_args()
    try:
        business,docs=read_manifest(a.manifest,business_dir=a.business_dir)
        print(json.dumps({'business':{k:len(v) for k,v in business.items()},'knowledge_documents':len(docs)},ensure_ascii=False))
    except (DataError,OSError) as exc:p.error(str(exc))
if __name__=='__main__':main()
