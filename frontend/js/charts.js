import {ApiError} from './api.js';
export function safePriceOptions(options) {
  const axis = Array.isArray(options?.xAxis) ? options.xAxis[0] : options?.xAxis;
  const series = options?.series?.[0];
  const labels = axis?.data, prices = series?.data;
  if (series?.type !== 'bar' || !Array.isArray(labels) || !Array.isArray(prices) || !labels.length || labels.length > 20 || labels.length !== prices.length) throw new ApiError('菜品图表数据格式无效。');
  const data = prices.map(x => typeof x === 'number' ? x : x?.value);
  if (data.some(x=>typeof x !== 'number' || !Number.isFinite(x) || x<0)) throw new ApiError('菜品价格无效。');
  return {animation:false, aria:{enabled:true}, color:['#8ba776'], grid:{left:46,right:20,top:28,bottom:65},
    tooltip:{trigger:'axis',renderMode:'richText'}, xAxis:{type:'category',data:labels.map(x=>String(x).slice(0,100)),axisLabel:{color:'#7e8e75',rotate:20,fontSize:10},axisLine:{lineStyle:{color:'#dfe7d9'}},axisTick:{show:false}},
    yAxis:{type:'value',name:'价格（元）',nameTextStyle:{color:'#8a9a81',fontSize:10},axisLabel:{color:'#8a9a81',fontSize:10},splitLine:{lineStyle:{color:'#edf1e8'}}},
    series:[{type:'bar',data,barMaxWidth:42,itemStyle:{borderRadius:[5,5,0,0]},label:{show:true,position:'top',color:'#749060',fontSize:11}}]};
}
export class Charts {
  constructor(api) { this.api = api; this.instances = new Map(); }
  async show(id, host) {
    const response = await this.api.chart(id);
    if (!host.isConnected) return;
    if (!globalThis.echarts) throw new ApiError('图表资源未加载，请检查vendor文件。');
    const options = safePriceOptions(response.options);
    const chart = echarts.init(host); const observer = new ResizeObserver(()=>chart.resize()); observer.observe(host);
    this.instances.set(host,{chart,observer}); chart.setOption(options);
  }
  clear() { for (const {chart,observer} of this.instances.values()) {observer.disconnect();chart.dispose();} this.instances.clear(); }
}
