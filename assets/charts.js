'use strict';

(() => {
  const source = window.CDT502_CHART_DATA;
  if (!window.echarts || !source) return;
  const color = { ...source.colors, total: '#8499b0', ink: '#253b50', muted: '#66788a', grid: '#e8edf2' };
  const outcome = ['有死亡或因伤住院', '未记录死亡或因伤住院'];
  const labels = { bubble:'材料报告数量与伤亡比例', paired: '数量与区间', stacked: '百分比构成', sankey: '桑基图' };
  const captions = {
    bubble:'材料标签旁的气泡面积表示该类全部报告数，旁边列出份数。右侧深红圆点表示伤亡比例，横线为95%置信区间；最右列给出伤亡比例与伤亡／全部报告份数。',
    paired: '左侧条形表示各类全部报告数；右侧圆点表示伤亡比例，横线为 Wilson 95% 置信区间。右侧数字依次为比例、伤亡报告数／该类全部报告数。',
    stacked: '每行都是该类的全部报告（100%），深红为伤亡报告，浅青为其余报告。横线为 Wilson 95% 置信区间，右侧保留比例和原始计数。',
    sankey: '每类报告按伤亡结果分成两条流带，宽度表示报告份数。深红为伤亡报告，浅青为其余报告；类别旁标出伤亡份数和伤亡比例。'
  };
  const charts = new Map();
  const number = n => n.toLocaleString('zh-CN');
  const percent = n => `${n.toFixed(1)}%`;
  const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
  const detail = row => `<strong>${escape(row.label)}</strong><br/>全部报告：${number(row.n)} 份<br/>伤亡报告：${number(row.k)} 份<br/>未记录死亡或因伤住院：${number(row.other)} 份<br/>伤亡比例：${row.k} ÷ ${row.n} = <b>${percent(row.rate)}</b><br/>Wilson 95% 置信区间：${percent(row.low)}—${percent(row.high)}`;

  const jointElement = document.getElementById('joint-chart');
  if (jointElement) {
    const chart = echarts.init(jointElement, null, {renderer:'canvas'});
    const cells = source.joint.cells;
    const n = cells.reduce((sum, row) => sum + row.n, 0);
    const k = cells.reduce((sum, row) => sum + row.k, 0);
    const otherParts = source.dimensions.component.filter(row => !['MAIN','SERVICE'].includes(row.category));
    const component = [...source.dimensions.component.filter(row => ['MAIN','SERVICE'].includes(row.category)), {category:'__others__',label:'其余8类部件'}];
    const status = document.getElementById('joint-status');
    status.textContent = '';
    jointElement.style.height = '540px';
    const nodes = [], links = [];
    for (const [dimension, field, depth] of [['component','part',0],['location','place',2]]) {
      for (const row of dimension === 'component' ? component : source.dimensions.location) {
        const subset = cells.filter(cell => cell[field] === row.category || (row.category === '__others__' && !['MAIN','SERVICE'].includes(cell.part)));
        const d = {n:subset.reduce((sum, cell) => sum + cell.n, 0),k:subset.reduce((sum, cell) => sum + cell.k, 0)};
        nodes.push({name:field+':'+row.category,depth,value:d.n,...d,display:row.label,others:row.category==='__others__',
          itemStyle:{color:color.total},label:{position:depth?'right':'left',formatter:`${row.label}\n${number(d.n)} 份 · 伤亡 ${number(d.k)} 份（${percent(100*d.k/d.n)}）`,show:false,fontSize:12,lineHeight:20}});
        for (let outcomeIndex=0; outcomeIndex<2; outcomeIndex++) {
          const value=outcomeIndex?d.n-d.k:d.k;
          if (!value) continue;
          links.push({source:depth?'outcome:'+outcomeIndex:'part:'+row.category,target:depth?'place:'+row.category:'outcome:'+outcomeIndex,
            value,display:row.label,outcomeIndex,denominator:outcomeIndex?n-k:k,dimension,categoryN:d.n,categoryK:d.k,others:row.category==='__others__',
            lineStyle:{color:outcomeIndex?color.other:color.case,opacity:outcomeIndex?.72:.82}});
        }
      }
    }
    for (let j=0;j<2;j++) {
      const value=j?n-k:k;
      nodes.push({name:'outcome:'+j,depth:1,value,display:j?'其余报告':'伤亡报告',
        label:{formatter:`${j?'其余报告':'伤亡报告'}\n${number(value)} 份`,position:'right',fontSize:15,fontWeight:600,lineHeight:25,backgroundColor:'#fffffff0',padding:[4,6]},itemStyle:{color:j?color.other:color.case}});
    }
    function drawJoint() {
      chart.resize();
      chart.setOption({...base(),animation:false,
        graphic:[],
        tooltip:{...base().tooltip,formatter:p=>{
          const d=p.data;
          if(p.dataType==='edge') {
            const result=d.outcomeIndex?'其余报告':'伤亡报告';
            const details=d.others?'<br>'+otherParts.map(row=>`${escape(row.label)}：${d.outcomeIndex?row.other:row.k}份`).join('<br>'):'';
            return `<strong>${escape(result)}中的${escape(d.display)}</strong><br>${d.value} 份，占该类全部 ${d.categoryN} 份的 ${percent(100*d.value/d.categoryN)}${details}`;
          }
          if(d.n!==undefined) {
            const details=d.others?'<br>'+otherParts.map(row=>`${escape(row.label)}：${row.n}份，其中伤亡${row.k}份`).join('<br>'):'';
            return `<strong>${escape(d.display)}</strong><br>全部 ${d.n} 份，其中伤亡 ${d.k} 份${details}`;
          }
          return `${escape(d.display)}：${d.value} 份<br>左右分别汇总，不追踪部件与地点之间的联合路径。`;
        }},
        series:[{type:'sankey',data:nodes,links,left:220,right:246,top:82,bottom:46,nodeWidth:13,nodeGap:42,layoutIterations:0,
          draggable:false,nodeAlign:'justify',lineStyle:{curveness:.48},emphasis:{focus:'none'},label:{color:color.ink}}]
      },{notMerge:true});
      const width=chart.getWidth(), graphics=[], glyphs=[];
      const txt=(x,y,text,size=12,fill=color.ink,weight=400)=>({type:'text',silent:true,style:{x,y,text,font:`${weight} ${size}px Microsoft YaHei`,fill,verticalAlign:'middle'}});
      graphics.push(txt(16,17,'部件',13,color.ink,600),txt(width-226,17,'地点',13,color.ink,600),
        txt(width/2-28,17,'人员后果',13,color.ink,600),
        txt(16,43,'各类内部的伤亡比例 · 等长条为100%',11,color.muted),
        txt(width-226,43,'各类内部的伤亡比例 · 等长条为100%',11,color.muted));
      const graph=chart.getModel().getSeriesByIndex(0).getGraph();
      graph.eachNode(node=>{
        const data=node.getModel().option;
        if(data.n===undefined)return;
        const layout=node.getLayout(),y=82+layout.y+layout.dy/2,x=layout.depth===0?16:width-226;
        const name=data.display.replace('公用设施通行权 / 地役权区域','公用设施通行权区域');
        const ratio=data.k/data.n;
        graphics.push(txt(x,y-25,name,12.5,color.ink,600),
          {type:'rect',silent:true,shape:{x,y:y-6,width:120,height:10,r:1},style:{fill:color.other}},
          {type:'rect',silent:true,shape:{x,y:y-6,width:120*ratio,height:10,r:1},style:{fill:color.case}},
          txt(x+128,y-1,percent(100*ratio),12.5,color.case,600),
          txt(x,y+18,`伤亡 ${data.k} ／ 全部 ${data.n} 份`,11.5,color.muted));
        glyphs.push({category:data.name,n:data.n,k:data.k,rate:ratio,width:120,redWidth:120*ratio});
      });
      chart.setOption({graphic:graphics},{replaceMerge:['graphic']});
      chart.__jointState={n,k,componentGroups:component.map(row=>row.category),nodes,links,glyphs};
      jointElement.dataset.n=n; jointElement.dataset.k=k;
      jointElement.setAttribute('aria-label','1550份事故报告。中间伤亡369份、其余1181份。左右分别按部件和地点汇总数量；类别旁的等长条显示各类内部的伤亡比例。部件与地点的实际对应关系见下一图。');

    }
    document.getElementById('joint-download')?.addEventListener('click',()=>{const a=document.createElement('a');a.download='全样本部件与地点构成.png';a.href=chart.getDataURL({pixelRatio:3,backgroundColor:'#fff'});a.click();});
    new ResizeObserver(drawJoint).observe(jointElement);
    drawJoint();
  }

  function tooltip(params) {
    const items = Array.isArray(params) ? params : [params];
    const item = items.find(p => p.data?.row);
    if (item) {
      const flow = item.data.flow === undefined ? '' : `<br/><br/>所选流带：${escape(item.data.flow)}，${number(item.data.value)} 份`;
      return detail(item.data.row) + flow;
    }
    const p = items[0];
    return `<strong>${escape(p.name)}</strong><br/>${number(p.value)} 份报告`;
  }

  function base() {
    return {
      animation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
      animationDuration: 420, animationDurationUpdate: 300,
      backgroundColor: '#ffffff', textStyle: { fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif', color: color.ink },
      tooltip: { trigger: 'item', confine: true, formatter: tooltip, borderColor: '#d6e0e8', backgroundColor: '#fffffffa', textStyle: { color: color.ink, fontSize: 13 }, extraCssText: 'line-height:1.9;box-shadow:0 5px 24px #253b5018;' }
    };
  }

  function valueAxis(gridIndex, isRate = true) {
    return {
      type: 'value', gridIndex, min: 0, ...(isRate ? { max: 100, interval: 20 } : {}),
      name: isRate ? '伤亡报告占该类全部报告（%）' : '该类全部报告（份）',
      nameLocation: 'middle', nameGap: 34, nameTextStyle: { fontSize: 12, color: color.muted },
      axisLine: { show: true, lineStyle: { color: '#bcc8d4' } }, axisTick: { show: false },
      axisLabel: { color: color.muted, fontSize: 12, formatter: v => isRate ? `${v}%` : number(v) },
      splitLine: { show: isRate, lineStyle: { color: color.grid } }
    };
  }

  function categoryAxis(rows, gridIndex, showLabels = true) {
    return { type: 'category', gridIndex, inverse: true, data: rows.map(r => r.label),
      axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false },
      axisLabel: { show: showLabels, margin: 16, color: color.ink, fontSize: 12, width: 194, overflow: 'break', lineHeight: 17 } };
  }

  function intervals(rows, axis) {
    return { type: 'custom', name: 'Wilson 95% 置信区间', xAxisIndex: axis, yAxisIndex: axis, silent: true, z: 4,
      data: rows.map((r, i) => ({ value: [r.low, r.high, i], row: r })),
      renderItem: (_, api) => {
        const start = api.coord([api.value(0), api.value(2)]);
        const end = api.coord([api.value(1), api.value(2)]);
        const style = { stroke: '#465e76', lineWidth: 1.4 };
        return { type: 'group', children: [
          { type: 'line', shape: { x1: start[0], y1: start[1], x2: end[0], y2: end[1] }, style },
          ...[start, end].map(p => ({ type: 'line', shape: { x1: p[0], y1: p[1]-4, x2: p[0], y2: p[1]+4 }, style }))
        ] };
      }
    };
  }

  function resultLabels(rows, axis) {
    return { type: 'custom', silent: true, xAxisIndex: axis, yAxisIndex: axis, clip: false, z: 6,
      data: rows.map((r, i) => [100, i]),
      renderItem: (params, api) => {
        const row = rows[params.dataIndex];
        const at = api.coord([100, api.value(1)]);
        return { type: 'text', style: { x: at[0]+18, y: at[1], text: `${percent(row.rate)}   ${row.k}/${row.n}`, font: '12px Microsoft YaHei', fill: color.ink, align: 'left', verticalAlign: 'middle' } };
      }
    };
  }

  function cartesian(rows, width, mode) {
    const paired = mode === 'paired';
    const left = 208, right = 158, gap = 75;
    const panel = (width - left - right - gap)/2;
    const grid = paired ? [
      { left, width: panel, top: 40, bottom: 78 },
      { left: left+panel+gap, right, top: 40, bottom: 78 }
    ] : [{ left, right, top: 52, bottom: 78 }];
    const axis = paired ? 1 : 0;
    const option = { ...base(), grid,
      graphic: [{ type: 'text', left: width-right+18, top: 16, style: { text: '比例    伤亡／全部', font: '12px Microsoft YaHei', fill: color.muted } }],
      xAxis: paired ? [valueAxis(0, false), valueAxis(1)] : [valueAxis(0)],
      yAxis: paired ? [categoryAxis(rows, 0), categoryAxis(rows, 1, false)] : [categoryAxis(rows, 0)],
      tooltip: { ...base().tooltip, trigger: 'axis', axisPointer: { type: 'shadow', axis: 'y', shadowStyle: { color: '#eef3f84d' } } },
      series: []
    };
    if (paired) {
      option.series.push({ type: 'bar', name: '该类全部报告', xAxisIndex: 0, yAxisIndex: 0,
        data: rows.map(r => ({ value: r.n, row: r })), barWidth: 19,
        itemStyle: { color: color.total, borderRadius: [0, 3, 3, 0] },
        label: { show: true, position: 'right', distance: 7, color: color.ink, fontSize: 12, formatter: p => number(p.value) } });
    }
    if (mode === 'stacked') {
      option.legend = { data: outcome, top: 0, left, selectedMode: false, icon: 'roundRect', itemWidth: 14, itemHeight: 10, textStyle: { fontSize: 12, color: color.muted } };
      for (let j = 0; j < 2; j++) {
        option.series.push({ type: 'bar', name: outcome[j], stack: 'all', barWidth: 24,
          data: rows.map(r => ({ value: j ? 100-r.rate : r.rate, row: r })),
          itemStyle: { color: j ? color.other : color.case }, emphasis: { disabled: true } });
      }
    } else {
      option.series.push({ type: 'scatter', name: '伤亡比例', xAxisIndex: axis, yAxisIndex: axis, z: 5,
        data: rows.map((r, i) => ({ value: [r.rate, i], row: r })), symbolSize: 9,
        itemStyle: { color: color.case, borderColor: '#fff', borderWidth: 1 }, emphasis: { scale: false } });
    }
    option.series.push(intervals(rows, axis), resultLabels(rows, axis));
    return option;
  }

  function bubble(rows, width) {
    const left=285, right=160, maximum=Math.max(...rows.map(r=>r.n));
    return {...base(), grid:{left,right,top:48,bottom:68},
      xAxis:{...valueAxis(0),name:'伤亡报告占该材料全部报告（%）'},
      yAxis:categoryAxis(rows,0,false),
      graphic:[
        {type:'text',left:16,top:8,style:{text:'材料',fill:color.muted,font:'12px Microsoft YaHei'}},
        {type:'text',left:147,top:8,style:{text:'全部报告（份）',fill:color.muted,font:'12px Microsoft YaHei'}},
        {type:'text',left:width-right+18,top:8,style:{text:'比例    伤亡／全部',fill:color.muted,font:'12px Microsoft YaHei'}}
      ],
      series:[
        {type:'custom',name:'材料与报告数量',clip:false,
          data:rows.map((r,i)=>({value:[0,i,r.n],row:r})),
          renderItem:(params,api)=>{
            const row=rows[params.dataIndex], y=api.coord([0,api.value(1)])[1];
            return {type:'group',children:[
              {type:'text',style:{x:16,y,text:row.label,verticalAlign:'middle',fill:color.ink,font:'13px Microsoft YaHei'}},
              {type:'circle',shape:{cx:177,cy:y,r:22*Math.sqrt(row.n/maximum)},style:{fill:'#d6e0e9',stroke:color.total,lineWidth:1}},
              {type:'text',style:{x:215,y,text:number(row.n),verticalAlign:'middle',fill:color.ink,font:'13px Microsoft YaHei'}}
            ]};
          }},
        intervals(rows,0),
        {type:'scatter',name:'伤亡比例',z:5,symbolSize:9,
          data:rows.map((r,i)=>({value:[r.rate,i],row:r})),
          itemStyle:{color:color.case,borderColor:'#fff',borderWidth:1},emphasis:{scale:false}},
        resultLabels(rows,0)
      ]};
  }

  function sankey(rows) {
    const nodes = rows.map((r, i) => ({ name: `category-${i}`, value: r.n, row: r,
      label: { position: 'left', formatter: `{name|${r.label}}  {count|${number(r.n)} 份}\n{stat|有伤亡 ${r.k} 份 · ${percent(r.rate)}}` }, itemStyle: { color: color.total } }));
    nodes.push(...outcome.map((name, j) => ({ name, value: j ? source.reports-source.casualty_reports : source.casualty_reports,
      label: { position: 'right', formatter: `{name|${name}}\n{total|${number(j ? source.reports-source.casualty_reports : source.casualty_reports)} 份}` }, itemStyle: { color: j ? color.other : color.case } })));
    const links = rows.flatMap((r, i) => [r.k, r.other].map((value, j) => ({ source: `category-${i}`, target: outcome[j], value, row: r, flow: outcome[j],
      lineStyle: { color: j ? color.other : color.case, opacity: j ? 0.82 : 0.85 } })).filter(link => link.value > 0));
    return { ...base(), series: [{ type: 'sankey', left: 270, right: 205, top: 25, bottom: 25,
      animationDuration: 350, animationDurationUpdate: 350, animationEasing: 'cubicOut',
      data: nodes, links, nodeWidth: 12, nodeGap: 42, nodeAlign: 'justify', layoutIterations: 0,
      draggable: false, label: { color: color.ink, lineHeight: 19, rich: {
        name: { fontSize: 13, fontWeight: 600, color: color.ink }, count: { fontSize: 12, color: color.muted },
        stat: { fontSize: 11, color: color.muted }, total: { fontSize: 20, fontWeight: 600, color: color.ink, lineHeight: 30 }
      } },
      lineStyle: { curveness: 0.48 }, emphasis: { focus: 'adjacency', lineStyle: { opacity: 1 } } }] };
  }

  function render(entry) {
    const rows = source.dimensions[entry.key];
    const mode = entry.figure.dataset.chartMode;
    entry.mode = mode;
    const height = mode === 'bubble' ? 500 : mode === 'sankey' ? Math.max(440, 140+rows.length*64) : Math.max(440, 140+rows.length*48);
    entry.element.style.height = `${height}px`;
    entry.chart.resize();
    const option = mode === 'bubble' ? bubble(rows,entry.element.clientWidth) : mode === 'sankey' ? sankey(rows) : cartesian(rows, entry.element.clientWidth, mode);
    entry.chart.setOption(option, { notMerge: true });
    entry.figure.dataset.chartMode = mode;
    const modeCaption = entry.figure.querySelector('.chart-caption');
    if (modeCaption) modeCaption.textContent = captions[mode];
    entry.element.setAttribute('aria-label', `${labels[mode]}。${rows.map(r => `${r.label}：${r.k}/${r.n}，${percent(r.rate)}`).join('；')}`);
  }

  for (const element of document.querySelectorAll('[data-chart-mode] .echart')) {
    const key = element.dataset.key;
    const figure = element.closest('figure');
    element.style.display = 'block';
    const entry = { key, element, figure, chart: echarts.init(element, null, { renderer: 'canvas' }) };
    charts.set(key, entry);
    render(entry);
    figure.classList.add('chart-ready');
    figure.querySelector('.chart-download').hidden = false;
  }

  for (const button of document.querySelectorAll('[data-chart-mode] [data-download-chart]')) {
    button.addEventListener('click', () => {
      const entry = charts.get(button.dataset.downloadChart);
      const anchor = document.createElement('a');
      anchor.download = `${entry.key}_${entry.mode}.png`;
      anchor.href = entry.chart.getDataURL({ type: 'png', pixelRatio: 3, backgroundColor: '#fff' });
      anchor.click();
    });
  }
  const observer = new ResizeObserver(entries => {
    for (const item of entries) {
      const entry = charts.get(item.target.dataset.key);
      if (entry && item.contentRect.width > 0 && entry.chart.getWidth() !== item.contentRect.width) render(entry);
    }
  });
  for (const entry of charts.values()) observer.observe(entry.element);
})();
