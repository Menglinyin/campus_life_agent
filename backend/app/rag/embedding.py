import hashlib, numpy as np
from .embedding_validation import validate_vectors, verify_lengths
class Embedding:
    dimension=1024
    def __init__(self,settings):
        self.settings=settings; self.model=None; self.tokenizer=None
        if settings.embedding_backend=="bge":
            from FlagEmbedding import BGEM3FlagModel
            self.model=BGEM3FlagModel(settings.embedding_model,use_fp16=settings.embedding_fp16)
            self.tokenizer=self.model.tokenizer
    def encode(self,texts):
        if not texts: return np.empty((0,self.dimension),dtype=np.float32)
        if self.model:
            verify_lengths(texts,self.tokenizer,self.settings.embedding_max_tokens)
            values=self.model.encode(texts,batch_size=8,max_length=self.settings.embedding_max_tokens,return_dense=True,return_sparse=False,return_colbert_vecs=False)["dense_vecs"]
        else:
            # Stable character hashing is ONLY a dependency-light test double.
            values=np.zeros((len(texts),self.dimension),dtype=np.float32)
            for i,text in enumerate(texts):
                if not text.strip(): raise ValueError("Empty text")
                if len(text)+2>self.settings.embedding_max_tokens: raise ValueError("Demo input too long")
                for c in text:
                    index=int.from_bytes(hashlib.sha256(c.encode()).digest()[:4],"big")%self.dimension
                    values[i,index]+=1
        return validate_vectors(values,len(texts),self.dimension)
