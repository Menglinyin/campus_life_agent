def business_answer(results):
    labels={'query_classrooms':'空闲教室','query_courses':'可旁听课程','recommend_dishes':'符合条件的菜品','query_secondhand':'在售二手物品'}
    lines=[]
    for result in results:
        name=result['tool']; lines.append(labels.get(name,'查询结果')+'：')
        rows=result.get('rows',[])
        if not rows: lines.append('没有查到符合条件的数据。')
        for row in rows:
            title=str(row.get('name','未命名'))
            if name=='query_classrooms': lines.append(f"{title}，日期 {row.get('date','未知')}，座位 {row.get('seats','未知')}。")
            elif name=='query_courses': lines.append(f"{title}，{row.get('date','')} {row.get('time','')}，地点 {row.get('room','未知')}。旁听前请征得任课老师同意。")
            elif name=='recommend_dishes': lines.append(f"{title}，{row.get('price','未知')} 元，辣度 {row.get('spice','未知')}。")
            elif name=='query_secondhand': lines.append(f"{title}，{row.get('price','未知')} 元。请自行核实物品状态。")
    return '\n'.join(lines)
