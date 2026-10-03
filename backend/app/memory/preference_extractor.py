import re
def extract_preferences(text):
    out={}
    if "不吃辣" in text: out["spice"]=0
    elif "微辣" in text: out["spice"]=1
    elif "能吃辣" in text: out["spice"]=2
    if "只吃素" in text: out["vegetarian"]=True
    elif "不再吃素" in text: out["vegetarian"]=False
    m=re.search(r"预算(?:是|为)?\s*(\d{1,3})(?:元|块)",text)
    if m: out["budget"]=int(m.group(1))
    return out
