from app.storage.models import Preference, User
class Preferences:
    def __init__(self,db): self.db=db
    def get(self,user):
        with self.db.transaction() as s:
            p=s.get(Preference,user); return dict(p.values) if p else {}
    def update(self,user,values):
        with self.db.transaction() as s:
            if not s.get(User,user): s.add(User(id=user)); s.flush()
            p=s.get(Preference,user)
            if p: p.values={**p.values,**values}
            else: s.add(Preference(user_id=user,values=values))
