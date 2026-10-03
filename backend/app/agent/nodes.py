import json,re
from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
from app.agent.prompts import SYSTEM
from app.mcp.schema_adapter import TOOLS
from app.memory.summary import recent_messages

def parse_date(text):
    today=datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if "后天" in text: return (today+timedelta(days=2)).isoformat()
    if "明天" in text: return (today+timedelta(days=1)).isoformat()
    if "今天" in text: return today.isoformat()
    m=re.search(r"\d{4}-\d{2}-\d{2}",text)
    if m: return date.fromisoformat(m.group()).isoformat()
    return None

def intents(text):
    if any(word in text for word in ['规则','规范','制度','须知']): return ['search_knowledge']
    names=[]
    for tokens,name in [(('教室',),'query_classrooms'),(('菜','食堂','吃饭','午饭','晚饭'),'recommend_dishes'),(('旁听','蹭课','课程'),'query_courses'),(('二手','交易'),'query_secondhand')]:
        if any(t in text for t in tokens): names.append(name)
    return names or ['search_knowledge']

class Nodes:
    def __init__(self,services): self.s=services
    async def prepare(self,state):
        slots=dict(state.get('slots',{})); found=parse_date(state['text'])
        if found: slots['date']=found
        names=intents(state['text'])
        if names==['search_knowledge'] and found and slots.get('pending'): names=slots.pop('pending')
        kinds=[{'query_classrooms':'classrooms','recommend_dishes':'dishes','query_courses':'courses','query_secondhand':'secondhand'}.get(n,'knowledge') for n in names]
        skills=self.s.skills.load(kinds)
        messages=[{'role':'system','content':SYSTEM+'\n技能：'+skills+'\n已确认日期与偏好：'+json.dumps({'slots':slots,'preferences':state['preferences']},ensure_ascii=False)}]
        messages+=recent_messages(state['history'],self.s.settings.history_turns)
        messages.append({'role':'user','content':state['text']})
        calls=[{'id':str(i),'function':{'name':n,'arguments':json.dumps({'date':slots.get('date'),'query':state['text'] if n=='search_knowledge' else ''})}} for i,n in enumerate(names)]
        return {'slots':slots,'messages':messages,'calls':calls,'results':[],'steps':0,'skills':skills}
    async def plan(self,state):
        if not self.s.settings.llm_base_url: return {}
        message=await self.s.model.chat(state['messages'],TOOLS)
        calls=message.get('tool_calls') or []
        if not calls and state['steps']==0 and any(c['function']['name']!='search_knowledge' for c in state['calls']):
            calls=state['calls']
            message={'role':'assistant','content':None,'tool_calls':[dict(c,type='function') for c in calls]}
        return {'calls':calls,'answer':message.get('content') or '', 'messages':state['messages']+[message]}
    async def execute(self,state):
        results=list(state['results']); messages=list(state['messages']); slots=dict(state['slots']); needs=[]
        if len(state['calls'])>4: raise ValueError('Too many tool calls')
        for call in state['calls']:
            name=call['function']['name']; args=json.loads(call['function']['arguments'])
            if not isinstance(args,dict): raise ValueError('Invalid tool arguments')
            if not args.get('date') and slots.get('date'): args['date']=slots['date']
            # Explicit message date wins over a conflicting generated date.
            if name in {'query_classrooms','recommend_dishes','query_courses'}: args['date']=slots.get('date')
            result=await self.s.executor.execute(name,args,state['user'],state['preferences'])
            if result.get('needs_date'): needs.append(name)
            else: results.append({'tool':name,**result})
            if self.s.settings.llm_base_url:
                messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
        if needs: slots['pending']=needs
        else: slots.pop('pending',None)
        return {'results':results,'messages':messages,'slots':slots,'steps':state['steps']+1,'answer':'请告诉我查询哪一天，例如“今天”或“2026-10-03”。' if needs else ''}
    async def respond(self,state):
        business=[r for r in state['results'] if r['tool']!='search_knowledge']
        if business and not state['slots'].get('pending'):
            from .formatting import business_answer
            return {'answer':business_answer(business)}
        if state.get('answer'): return {}
        if self.s.settings.llm_base_url: return {'answer':'已达到工具调用上限，请简化问题后重试。'}
        lines=[]
        for result in state['results']:
            rows=result.get('rows',[])
            if not rows: lines.append('没有查到符合条件的数据。'); continue
            if result['tool']=='search_knowledge':
                lines.extend(f"{x['text']}（来源：{x['source']}）" for x in rows)
            else:
                lines.append(result['tool']+'：')
                lines.extend(json.dumps(x,ensure_ascii=False) for x in rows)
        return {'answer':'\n'.join(lines) or '暂无可用结果。'}
