from sqlalchemy import select
from app.storage.models import Classroom, Course, Dish, SecondhandListing
class CampusServices:
    classes={"classrooms":Classroom,"courses":Course,"dishes":Dish,"secondhand":SecondhandListing}
    def __init__(self,db): self.db=db
    def list(self,kind,date=None):
        with self.db.transaction() as s:
            rows=[dict(x.payload,id=x.id) for x in s.scalars(select(self.classes[kind]))]
        return [x for x in rows if date is None or x.get("date")==date]
