from uuid import uuid4
from sqlalchemy import select
from fastapi import HTTPException
from app.storage.models import User, Conversation, Message
class Conversations:
    def __init__(self, db): self.db=db
    def ensure(self, user, session_id=None):
        with self.db.transaction() as s:
            if not s.get(User,user): s.add(User(id=user)); s.flush()
            if session_id:
                chat=s.get(Conversation,session_id)
                if not chat or chat.user_id!=user: raise HTTPException(404,"Session not found")
                return chat.id
            sid=str(uuid4()); s.add(Conversation(id=sid,user_id=user,slots={},version=0)); return sid
    def snapshot(self, user, sid):
        with self.db.transaction() as s:
            chat=s.get(Conversation,sid)
            if not chat or chat.user_id!=user: raise HTTPException(404,"Session not found")
            messages=s.scalars(select(Message).where(Message.session_id==sid).order_by(Message.created_at,Message.id)).all()
            return {"version":chat.version,"slots":chat.slots,"messages":[{"id":m.id,"role":m.role,"content":m.content,"payload":m.payload} for m in messages]}
    def save_turn(self, user, sid, question, answer, payload, slots, expected_version):
        with self.db.transaction() as s:
            chat=s.scalar(select(Conversation).where(Conversation.id==sid,Conversation.user_id==user).with_for_update())
            if not chat: raise HTTPException(404,"Session not found")
            if chat.version!=expected_version: raise HTTPException(409,"Session changed; retry")
            mid=str(uuid4())
            s.add(Message(id=str(uuid4()),session_id=sid,role="user",content=question,payload={}))
            s.add(Message(id=mid,session_id=sid,role="assistant",content=answer,payload=payload))
            chat.version+=1; chat.slots=slots
            return mid
    def assistant_message(self,user,mid):
        with self.db.transaction() as s:
            m=s.get(Message,mid)
            if not m or m.role!="assistant": raise HTTPException(404,"Message not found")
            c=s.get(Conversation,m.session_id)
            if c.user_id!=user: raise HTTPException(404,"Message not found")
            return {"content":m.content,"payload":m.payload}
