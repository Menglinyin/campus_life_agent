import json
from pyecharts.charts import Bar
from pyecharts import options as opts
from fastapi import HTTPException
def chart_options(results):
    rows=next((r['rows'] for r in results if r['tool']=='recommend_dishes'),[])
    if not rows: raise HTTPException(422,'This message has no dish price data')
    rows=rows[:20]
    if any('name' not in x or not isinstance(x.get('price'),(int,float)) for x in rows): raise HTTPException(422,'Invalid dish price data')
    chart=Bar().add_xaxis([str(x['name']) for x in rows]).add_yaxis('价格（元）',[float(x['price']) for x in rows]).set_global_opts(title_opts=opts.TitleOpts(title='菜品价格对比'))
    return json.loads(chart.dump_options_with_quotes())
