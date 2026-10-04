def run(runtime,args,user):
    if args.date is None:return {'needs_date':True,'rows':[]}
    rows=runtime.rows('courses',args.date.isoformat())
    rows=[r for r in rows if r['auditing_allowed'] and (not args.query or args.query in r['name'])]
    return {'rows':sorted(rows,key=lambda r:(r['time'],r['id']))[:10]}
