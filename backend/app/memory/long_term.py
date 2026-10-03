class LongTermMemory:
    def __init__(self,preferences,retriever): self.preferences=preferences; self.retriever=retriever
    def retrieve(self,user,query):
        return {"preferences":self.preferences.get(user),"knowledge":self.retriever.search(query,user)}
