import hashlib
class ChromaStore:
    def __init__(self,path,signature):
        import chromadb
        self.client=chromadb.PersistentClient(path=path)
        name="campus_"+hashlib.sha256(signature.encode()).hexdigest()[:16]
        self.collection=self.client.get_or_create_collection(name,metadata={"hnsw:space":"cosine"})
    def upsert(self,chunks,vectors):
        if chunks:
            self.collection.upsert(ids=[c["id"] for c in chunks],embeddings=vectors.tolist(),documents=[c["text"] for c in chunks],metadatas=[{"owner":c["owner"],"source":c["source"]} for c in chunks])
    def search(self,vector,user,k):
        result=self.collection.query(query_embeddings=[vector.tolist()],n_results=k,where={"owner":{"$in":["public",user]}})
        return result["ids"][0]
