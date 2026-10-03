import numpy as np
def validate_vectors(vectors,count,dimension=1024):
    a=np.asarray(vectors,dtype=np.float32)
    if a.shape!=(count,dimension) or not np.isfinite(a).all(): raise ValueError("Invalid embedding shape or non-finite vector")
    norms=np.linalg.norm(a,axis=1,keepdims=True)
    if (norms<1e-12).any(): raise ValueError("Zero embedding")
    return a/norms
def verify_lengths(texts,tokenizer,limit):
    lengths=[len(tokenizer.encode(t,add_special_tokens=True,truncation=False)) for t in texts]
    if any(n>limit for n in lengths): raise ValueError(f"Embedding input exceeds {limit} tokens; rechunk instead of truncating")
    return lengths
