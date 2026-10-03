def validate_result(result):
    if not isinstance(result,dict) or not isinstance(result.get("rows"),list): raise ValueError("Tool result must contain rows array")
    if len(result["rows"])>100 or not all(isinstance(x,dict) for x in result["rows"]): raise ValueError("Invalid tool result rows")
    return {**result,"rows":result["rows"][:20]}
