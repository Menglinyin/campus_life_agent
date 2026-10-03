from pathlib import Path
def read_document(path):
    p=Path(path)
    if p.suffix.lower() not in {".txt",".md"}: raise ValueError("Only UTF-8 TXT/Markdown supported; convert PDF/DOCX first")
    return p.read_text(encoding="utf-8")
