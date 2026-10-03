class Reranker:
    def __init__(self,model_name):
        self.model=None
        if model_name:
            from FlagEmbedding import FlagReranker
            self.model=FlagReranker(model_name,use_fp16=False)
    def rank(self,query,chunks,k):
        if self.model and chunks:
            scores=self.model.compute_score([[query,c["text"]] for c in chunks],normalize=True)
            if isinstance(scores,(float,int)): scores=[scores]
            chunks=[c for _,c in sorted(zip(scores,chunks),key=lambda p:p[0],reverse=True)]
        return chunks[:k]
