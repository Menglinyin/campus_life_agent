from threading import RLock
from . import backend  # noqa: F401
from .schemas import ClassroomRow,CourseRow,DishRow,SecondhandRow
from app.storage.mysql import Database
from app.storage.repositories.campus_services import CampusServices
from app.storage.repositories.preferences import Preferences
from app.storage.repositories.knowledge import Knowledge
from app.rag.embedding import Embedding
from app.rag.hybrid_retrieval import HybridRetriever

class Runtime:
    row_types={'classrooms':ClassroomRow,'courses':CourseRow,'dishes':DishRow,'secondhand':SecondhandRow}
    def __init__(self,settings,with_rag=False):
        self.settings=settings;self.db=Database(settings.database_url)
        try:
            self.db.initialize()
            self.campus=CampusServices(self.db);self.preferences=Preferences(self.db)
            self.rag_lock=RLock();self.rag=None
            if with_rag:self.rag=HybridRetriever(Knowledge(self.db),Embedding(settings),settings)
        except Exception:
            self.db.close();raise
    def rows(self,kind,date=None):
        rows=self.campus.list(kind,date)
        # Drop unapproved payload fields; invalid source data fails the tool.
        return [self.row_types[kind].model_validate(row).model_dump(mode='json') for row in rows]
    def knowledge(self,query,user):
        if self.rag is None:raise RuntimeError('Knowledge search unavailable')
        with self.rag_lock:return self.rag.search(query,user)
    def close(self):self.db.close()
