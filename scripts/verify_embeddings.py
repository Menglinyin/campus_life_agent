import sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import argparse
from scripts.common import load_settings,read_text,report,run_cli,config_args

def verify(profile='demo',env_file=None,file=None,chunk=True):
    import numpy as np
    from app.rag.embedding import Embedding
    from app.rag.chunking import chunk_text
    from app.rag.cleaning import clean_text
    from app.rag.embedding_validation import verify_lengths,validate_vectors
    settings=load_settings(profile,env_file);embedding=Embedding(settings)
    text=clean_text(read_text(file)) if file else '校园旁听规则：请征得任课教师同意。'
    parts=chunk_text(text,settings.chunk_tokens,settings.chunk_overlap,embedding.tokenizer) if chunk else [text]
    lengths=verify_lengths(parts,embedding.tokenizer,settings.embedding_max_tokens) if embedding.tokenizer else [len(part)+2 for part in parts]
    if any(length>settings.embedding_max_tokens for length in lengths):raise ValueError('Input exceeds embedding limit')
    values=embedding.encode(parts);validate_vectors(values,len(parts),embedding.dimension)
    norms=np.linalg.norm(values,axis=1)
    return {'backend':settings.embedding_backend,'test_double':settings.embedding_backend=='demo','chunks':len(parts),'dimension':values.shape[1],'dtype':str(values.dtype),'max_input_units_including_special_tokens':max(lengths),'units':'tokens' if embedding.tokenizer else 'demo_characters_plus_two','length_limit':settings.embedding_max_tokens,'finite':bool(np.isfinite(values).all()),'norm_min':float(norms.min()),'norm_max':float(norms.max()),'model_fp16_requested':settings.embedding_fp16,'text_or_vectors_exported':False,'database_connected':False,'truncation_used':False}

def main():
    p=argparse.ArgumentParser(description='Exercise actual embedding code and non-truncating length checks; no SQL/Chroma writes')
    config_args(p);p.add_argument('--file',type=Path);p.add_argument('--no-chunk',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();report(verify(a.profile,a.env_file,a.file,not a.no_chunk),a.output)
if __name__=='__main__':raise SystemExit(run_cli(main))
