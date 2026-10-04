from sqlalchemy import select
from mcp_servers.common import backend  # noqa: F401
from mcp_servers.common.idempotency import submit, public_review
from app.storage.models import Feedback

def submit_review(runtime,args,user):return submit(runtime,user,args)

def list_reviews(runtime,user):
    with runtime.db.transaction() as session:
        records=session.scalars(select(Feedback).where(Feedback.payload['user_id'].as_string()==user).order_by(Feedback.id).limit(20))
        return {'rows':[public_review(record) for record in records]}
