import json
from collections import Counter
def majority_tool_plan(plans):
    """Optional offline plan comparison; default online flow does not sample N plans."""
    canonical=[json.dumps(p,sort_keys=True,ensure_ascii=False) for p in plans]
    if not canonical: raise ValueError("No plans")
    return json.loads(Counter(canonical).most_common(1)[0][0])
