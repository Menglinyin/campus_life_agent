def recommend_dishes(rows,preferences):
    rows=[r for r in rows if r.get("available",False)]
    if "spice" in preferences: rows=[r for r in rows if r.get("spice",0)<=preferences["spice"]]
    if "budget" in preferences: rows=[r for r in rows if r["price"]<=preferences["budget"]]
    if preferences.get("vegetarian"): rows=[r for r in rows if r.get("vegetarian",False)]
    return sorted(rows,key=lambda r:(-r.get("rating",0),r["price"]))[:10]
