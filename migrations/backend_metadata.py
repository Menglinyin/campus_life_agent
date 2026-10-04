from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[1]
BACKEND=PROJECT/'backend'
if not (BACKEND/'app/storage/mysql.py').is_file():
    raise RuntimeError('Place migrations beside the completed backend directory')
if str(BACKEND) not in sys.path:sys.path.insert(0,str(BACKEND))
from app.storage.mysql import Base
from app.storage import models  # noqa: F401: register all 11 tables
metadata=Base.metadata
