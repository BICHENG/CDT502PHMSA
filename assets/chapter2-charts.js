'use strict';
(() => {
  const source = window.CDT502_CHAPTER2;
  if (!source || !window.echarts) return;
  const ink = '#193240', muted = '#536871', red = source.colors.case, cyan = source.colors.other;
  const charts = new Map();
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const result = row => `${row.rate.toFixed(1)}%   ${row.k} / ${row.n}`;

  function base() {
    return { animation: false, textStyle: {fontFamily:'Microsoft YaHei, sans-serif',color:ink},
      tooltip: {trigger:'item', backgroundColor:'#fff', borderColor:'#d6e0e1', textStyle:{color:ink,fontSize:13},
        formatter: p => {
          const row = p.data?.row;
          if (!row) return '';
          if (row.difference !== undefined) return `${escape(row.label)}<br>进户管高出 ${(row.difference*100).toFixed(1)} 个百分点<br>95% 区间：${(row.low*100).toFixed(1)} 至 ${(row.high*100).toFixed(1)}`;
          return `${escape(row.label)}${row.period && !row.label.includes(row.period) ? ' · '+escape(row.period) : ''}<br>伤亡报告：${row.k} 份<br>该组全部报告：${row.n} 份<br>伤亡比例：${row.rate.toFixed(1)}%<br>Wilson 95% 区间：${row.low.toFixed(1)}% 至 ${row.high.toFixed(1)}%`;
        }}, series: [] };
  }

  function xaxis(index, name, max=100) {
    return {type:'value', gridIndex:index, min:0, max, name, nameLocation:'middle', nameGap:36,
      nameTextStyle:{color:muted,fontSize:12}, axisLine:{show:true,lineStyle:{color:'#BAC9CD'}},
      axisTick:{show:false}, axisLabel:{color:muted,fontSize:11}, splitLine:{lineStyle:{color:'#E5EAEB'}}};
  }
  function yaxis(rows, index, labels=true) {
    return {type:'category',gridIndex:index,inverse:true,data:rows.map(r=>r.label),
      axisTick:{show:false},axisLine:{show:false},splitLine:{show:false},
      axisLabel:{show:labels,color:ink,fontSize:12,lineHeight:18,margin:13}};
  }
  function intervals(rows, index, gap=false) {
    return {type:'custom',xAxisIndex:index,yAxisIndex:index,z:6,clip:false,tooltip:{show:false},
      renderItem: (params, api) => {
        const low=api.coord([api.value(0),api.value(2)]), high=api.coord([api.value(1),api.value(2)]);
        return {type:'group',children:[
          {type:'line',shape:{x1:low[0],y1:low[1],x2:high[0],y2:high[1]},style:{stroke:ink,lineWidth:1.2}},
          ...[low,high].map(p=>({type:'line',shape:{x1:p[0],y1:p[1]-4,x2:p[0],y2:p[1]+4},style:{stroke:ink,lineWidth:1.2}}))]};
      },data:rows.map((r,i)=>[r.low*(gap?100:1),r.high*(gap?100:1),i])};
  }
  function proportions(rows,index,{bars=true,uncertainty=true}={}) {
    const series=[];
    if (bars) {
      for (let i=0;i<2;i++) series.push({type:'bar',xAxisIndex:index,yAxisIndex:index,stack:`outcome-${index}`,
        barWidth:22,name:i?'其余报告':'伤亡报告',itemStyle:{color:i?cyan:red},emphasis:{disabled:true},
        data:rows.map(r=>({value:i?100-r.rate:r.rate,row:r}))});
    } else series.push({type:'scatter',xAxisIndex:index,yAxisIndex:index,symbolSize:9,z:8,
      itemStyle:{color:red,borderColor:'#fff',borderWidth:1},data:rows.map((r,i)=>({value:[r.rate,i],row:r}))});
    if (uncertainty) series.push(intervals(rows,index));
    series.push({type:'scatter',xAxisIndex:index,yAxisIndex:index,symbolSize:0,clip:false,silent:true,
      label:{show:true,position:'right',distance:12,color:ink,fontSize:12,formatter:p=>result(p.data.row)},
      data:rows.map((r,i)=>({value:[100,i],row:r}))});
    return series;
  }

  function option(key,width) {
    const rows=source.tables[key], out=base();
    const top=25,bottom=68;
    if (key==='periods') {
      const left=175,gap=210,panel=(width-left-25-gap)/2;
      const gaps=source.gaps.slice(0,2).map((r,i)=>({...r,label:i?'2022年起':'2010–2021年'}));
      out.grid=[{left,width:panel,top,bottom},{left:left+panel+gap,right:25,top,bottom}];
      out.xAxis=[xaxis(0,'伤亡报告比例（%）'),xaxis(1,'进户管高出的百分点',60)];
      out.xAxis[1].splitLine={show:false};
      out.yAxis=[yaxis(rows,0),yaxis(gaps,1)];
      out.series=proportions(rows,0,{uncertainty:false});
      out.series.push(intervals(gaps,1,true),{type:'scatter',xAxisIndex:1,yAxisIndex:1,symbolSize:9,z:8,
        itemStyle:{color:red},label:{show:true,position:'top',distance:12,color:red,fontSize:14,formatter:p=>'+'+(p.data.row.difference*100).toFixed(1)},
        data:gaps.map((r,i)=>({value:[r.difference*100,i],row:r}))});
    } else if (key==='causes') {
      const left=210,right=160,gap=75,panel=(width-left-right-gap)/2;
      out.grid=[{left,width:panel,top,bottom},{left:left+panel+gap,right,top,bottom}];
      out.xAxis=[xaxis(0,'报告数量（份）',600),xaxis(1,'伤亡报告比例（%）')];
      out.xAxis[0].interval=200;
      out.yAxis=[yaxis(rows,0),yaxis(rows,1,false)];
      for(let i=0;i<2;i++) out.series.push({type:'bar',xAxisIndex:0,yAxisIndex:0,stack:'count',barWidth:20,
        itemStyle:{color:i?cyan:red},emphasis:{disabled:true},data:rows.map(r=>({value:i?r.other:r.k,row:r})),
        label:i?{show:true,position:'right',color:ink,fontSize:11,formatter:p=>p.data.row.n}:{show:false}});
      out.series.push(...proportions(rows,1,{bars:false}));
    } else if(key==='materials') {
      const left=110,right=150,gap=170,panel=(width-left-right-gap)/2;
      out.grid=[{left,width:panel,top,bottom},{left:left+panel+gap,right,top,bottom}];
      out.xAxis=[xaxis(0,'2010–2021年 · 伤亡报告比例（%）'),xaxis(1,'2022年起 · 伤亡报告比例（%）')];
      out.yAxis=[yaxis(rows.slice(0,3),0),yaxis(rows.slice(3),1,false)];
      out.series=[...proportions(rows.slice(0,3),0,{bars:false}),...proportions(rows.slice(3),1,{bars:false})];
    } else {
      out.grid=[{left:key==='locations'?290:170,right:160,top,bottom}];
      out.xAxis=[xaxis(0,'伤亡报告比例（%）')];out.yAxis=[yaxis(rows,0)];
      out.series=proportions(rows,0);
    }
    return out;
  }
  function render(entry) {
    entry.chart.resize();
    entry.chart.setOption(option(entry.key,entry.element.clientWidth),{notMerge:true});
  }
  for(const element of document.querySelectorAll('.chapter2-chart')) {
    element.style.display='block';
    const key=element.dataset.key,figure=element.closest('figure');
    const entry={key,element,figure,chart:echarts.init(element,null,{renderer:'canvas'})};
    charts.set(key,entry);render(entry);figure.classList.add('chart-ready');
    const button=figure.querySelector('.chart-download');button.hidden=false;
    button.addEventListener('click',()=>{
      const link=document.createElement('a');link.download=`chapter2_${key}.png`;
      link.href=entry.chart.getDataURL({type:'png',pixelRatio:3,backgroundColor:'#fff'});link.click();
    });
  }
  const observer=new ResizeObserver(entries=>{
    for(const item of entries){const entry=charts.get(item.target.dataset.key);
      if(entry && item.contentRect.width>0 && entry.chart.getWidth()!==item.contentRect.width)render(entry);}
  });
  for(const entry of charts.values())observer.observe(entry.element);
})();
