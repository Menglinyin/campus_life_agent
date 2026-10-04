def run(runtime,args,user):
    if args.date is None:return {'needs_date':True,'rows':[]}
    rows=runtime.rows('courses',args.date.isoformat())
    return {'rows':[r for r in rows if r['auditing_allowed']][:20]}
