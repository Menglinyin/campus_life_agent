import re, unicodedata
def clean_text(text):
    text=unicodedata.normalize("NFKC",text).replace("\x00","")
    return re.sub(r"[ \t]+"," ",text).strip()
