def run(runtime,args,user):
    rows=runtime.rows('secondhand')
    return {'rows':[r for r in rows if r['status']=='active' and (not args.query or args.query in r['name'])][:20]}
