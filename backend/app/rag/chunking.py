def chunk_text(text,size=512,overlap=64,tokenizer=None):
    if not 0<=overlap<size: raise ValueError("Invalid overlap")
    units=tokenizer.encode(text,add_special_tokens=False,truncation=False) if tokenizer else list(text)
    chunks=[]
    for start in range(0,len(units),size-overlap):
        segment=units[start:start+size]
        result=tokenizer.decode(segment,skip_special_tokens=True) if tokenizer else "".join(segment)
        if result.strip(): chunks.append(result)
        if start+size>=len(units): break
    return chunks
