def run(runtime,args,user):
    if args.date is None:return {'needs_date':True,'rows':[]}
    rows=runtime.rows('dishes',args.date.isoformat())
    return {'rows':[r for r in rows if r['available'] and (not args.query or args.query in r['name'])][:20]}
