import re
from datetime import date
import unicodedata
from voice.common.errors import InputError, SizeError

def normalize_text(text, maximum=1000):
    if not isinstance(text, str) or not text.strip(): raise InputError()
    if len(text) > maximum: raise SizeError()
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'<\|[^>]*\|>', '', text)
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://[^\s]+', ' ', text)
    text = re.sub(r'(?m)^\s*(?:#{1,6}\s+|[-*+]\s+)', '', text)
    text = re.sub(r'[*`_]', '', text)
    text = ''.join(c if c in '\n\t' or unicodedata.category(c) not in {'Cc', 'Cf'} else ' ' for c in text)
    def spoken_date(match):
        try: value = date.fromisoformat(match.group(0))
        except ValueError: return match.group(0)
        return f'{value.year}年{value.month}月{value.day}日'
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', spoken_date, text)
    def spoken_time(match):
        hour, minute = map(int, match.groups())
        if hour > 23 or minute > 59: return match.group(0)
        return f'{hour}点{minute}分' if minute else f'{hour}点整'
    text = re.sub(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)', spoken_time, text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text: raise InputError()
    return text

def split_text(text, limit=200):
    if limit < 1: raise ValueError('Invalid chunk limit')
    parts = re.findall(r'[^。！？!?；;]+[。！？!?；;]*|[。！？!?；;]+', text)
    chunks = []; pending = ''
    for part in parts:
        if pending and len(pending) + len(part) > limit:
            chunks.append(pending); pending = ''
        while len(part) > limit:
            if pending: chunks.append(pending); pending = ''
            chunks.append(part[:limit]); part = part[limit:]
        pending += part
    if pending: chunks.append(pending)
    return chunks
