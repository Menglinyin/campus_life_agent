def visible_chunks(chunks,user): return [c for c in chunks if c["owner"] in {"public",user}]
