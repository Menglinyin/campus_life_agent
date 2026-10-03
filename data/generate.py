import argparse,csv
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
FIELDS={
 'classrooms':['id','name','date','available','seats'],
 'courses':['id','name','date','room','time','auditing_allowed'],
 'dishes':['id','name','date','price','spice','vegetarian','rating','available'],
 'secondhand':['id','name','price','status']}
def generate(output,base_date,days=3):
    if not 1<=days<=31: raise ValueError('days must be between 1 and 31')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    rows={kind:[] for kind in FIELDS}
    for offset in range(days):
        day=base_date+timedelta(days=offset);stamp=day.strftime('%Y%m%d')
        for i in range(1,4): rows['classrooms'].append(dict(id=f'synthetic-room-{stamp}-{i}',name=f'合成教室A{i}01',date=day.isoformat(),available='true' if i!=2 else 'false',seats=30+i*10))
        for i in range(1,3):rows['courses'].append(dict(id=f'synthetic-course-{stamp}-{i}',name=['合成人工智能导论','合成通信原理'][i-1],date=day.isoformat(),room='合成教室A201',time=['09:00','14:00'][i-1],auditing_allowed='true' if i==1 else 'false'))
        dishes=[('合成番茄炒蛋',10,0,'true',4.8,'true'),('合成微辣鸡丁',15,1,'false',4.7,'true'),('合成青菜套餐',8,0,'true',4.5,'true'),('合成辣味鱼',18,2,'false',4.9,'false')]
        for i,(name,price,spice,vegetarian,rating,available) in enumerate(dishes,1): rows['dishes'].append(dict(id=f'synthetic-dish-{stamp}-{i}',name=name,date=day.isoformat(),price=price,spice=spice,vegetarian=vegetarian,rating=rating,available=available))
    for i,(name,price,status) in enumerate([('合成二手台灯',20,'active'),('合成二手教材',15,'active'),('合成二手键盘',30,'sold')],1): rows['secondhand'].append(dict(id=f'synthetic-item-{i}',name=name,price=price,status=status))
    for kind,values in rows.items():
        with (output/f'{kind}.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS[kind]);writer.writeheader();writer.writerows(values)
    return {k:len(v) for k,v in rows.items()}
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'local/generated');p.add_argument('--base-date',type=date.fromisoformat,default=datetime.now(ZoneInfo('Asia/Shanghai')).date());p.add_argument('--days',type=int,default=3);args=p.parse_args()
    try:print(generate(args.output,args.base_date,args.days))
    except ValueError as exc:p.error(str(exc))
if __name__=='__main__':main()
