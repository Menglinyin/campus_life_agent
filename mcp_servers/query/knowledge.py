def run(runtime,args,user):
    if not args.query.strip():raise ValueError('Query required')
    return {'rows':runtime.knowledge(args.query,user)}
