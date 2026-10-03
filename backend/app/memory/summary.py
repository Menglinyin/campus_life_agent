def recent_messages(messages,turns=10):
    return [{"role":m["role"],"content":m["content"][:2000]} for m in messages[-2*turns:]]
