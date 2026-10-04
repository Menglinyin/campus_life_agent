"""Import the existing backend, never copy its ORM/RAG implementations."""
from pathlib import Path
import sys
BACKEND=Path(__file__).resolve().parents[2]/'backend'
if not (BACKEND/'app/settings.py').is_file():
    raise RuntimeError('Place mcp_servers beside the completed backend directory')
if str(BACKEND) not in sys.path: sys.path.insert(0,str(BACKEND))
