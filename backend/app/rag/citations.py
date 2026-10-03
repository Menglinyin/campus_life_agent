def citations(chunks):
    return [{"id":c["id"],"source":c["source"],"text":c["text"]} for c in chunks]
