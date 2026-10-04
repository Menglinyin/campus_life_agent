"""Use the existing feedback primary key as a DB-backed idempotency guard."""
from datetime import datetime,timezone
import hashlib,json
from sqlalchemy.exc import IntegrityError
from . import backend  # noqa: F401
from app.storage.models import Feedback

def public_review(record):
    fields=('target_kind','target_id','rating','comment','created_at')
    return {'id':record.id,**{k:record.payload[k] for k in fields}}

def submit(runtime,user,args):
    values=args.model_dump(exclude={'idempotency_key'})
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    record_id=hashlib.sha256(('submit_review\0'+user+'\0'+args.idempotency_key).encode()).hexdigest()
    def existing():
        with runtime.db.transaction() as session:
            record=session.get(Feedback,record_id)
            if record is None:return None
            if record.payload.get('user_id')!=user or record.payload.get('request_hash')!=digest:
                raise ValueError('Idempotency key conflicts with previous request')
            return {'rows':[public_review(record)],'replayed':True}
    previous=existing()
    if previous:return previous
    cls=runtime.campus.classes[args.target_kind]
    try:
        with runtime.db.transaction() as session:
            if session.get(cls,args.target_id) is None:raise ValueError('Target not found')
            record=Feedback(id=record_id,payload={**values,'user_id':user,'request_hash':digest,'created_at':datetime.now(timezone.utc).isoformat()})
            session.add(record);session.flush()
            output={'rows':[public_review(record)],'replayed':False}
        return output
    except IntegrityError:
        # A competing process may have committed the same key while we inserted.
        previous=existing()
        if previous:return previous
        raise
