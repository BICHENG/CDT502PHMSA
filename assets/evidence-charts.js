(() => {
  'use strict';
  if (!window.echarts || !window.CDT502_EVIDENCE) return;
  const ink = '#173241', muted = '#526974', instances = [];
  const materialColors=['#96563E','#7D8994','#C1CDCF'];
  const materialTextures=materialColors.map((color,i)=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=32;
    const ctx=canvas.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,32,32);
    if(i===0){ctx.fillStyle='rgba(56,34,22,.24)';[[4,7],[17,3],[25,14],[9,22],[22,27]].forEach(([x,y])=>{ctx.beginPath();ctx.arc(x,y,1.2,0,2*Math.PI);ctx.fill();});}
    if(i===1){ctx.strokeStyle='rgba(235,240,243,.32)';ctx.lineWidth=.7;for(let y=2;y<32;y+=4){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(32,y);ctx.stroke();}}
    return {image:canvas,repeat:'repeat'};
  });
  function contextOption(spec,width,height) {
    const base={animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei, sans-serif'},
      tooltip:{trigger:'axis',confine:true},grid:{left:100,right:150,top:48,bottom:65}};
    const valueAxis={type:'value',min:0,axisLabel:{color:muted},axisTick:{show:false},
      axisLine:{show:true,lineStyle:{color:'#BDCAD1'}},splitLine:{lineStyle:{color:'#E6EBEE'}},
      nameTextStyle:{color:ink,fontSize:12}};
    if(spec.kind==='history') {
      base.grid={left:86,right:230,top:58,bottom:60};
      base.legend={top:7,left:86,selectedMode:false,textStyle:{color:ink,fontSize:12},data:spec.series.map(s=>s.name)};
      base.xAxis={type:'category',data:spec.years.map(String),boundaryGap:false,name:'年',nameLocation:'middle',nameGap:30,nameTextStyle:{color:ink},axisLabel:{color:muted,interval:4,showMaxLabel:true},axisTick:{show:false},axisLine:{lineStyle:{color:'#BDCAD1'}}};
      base.yAxis={...valueAxis,max:155,interval:30,name:'在用主管道里程（万英里）',nameLocation:'middle',nameGap:52};
      base.tooltip.formatter=items=>{const j=items[0].dataIndex;return `${spec.years[j]} 年 · 三类主要材料<br>`+spec.series.map(s=>`${s.name}：${s.values[j].toFixed(2)} 万英里（${s.shares[j].toFixed(1)}%）`).join('<br>')+`<br>三类合计：${spec.total[j].toFixed(2)} 万英里<br>每层厚度为单项材料，上边界为累计值`;};
      base.series=spec.series.map((s,i)=>({type:'line',name:s.name,stack:'三类主要材料',showSymbol:false,lineStyle:{width:1,color:'#fff'},itemStyle:{color:materialColors[i]},
        areaStyle:{color:materialTextures[i],opacity:1},emphasis:{disabled:true},data:s.values,
        markLine:i===0?{silent:true,symbol:'none',label:{formatter:'事故率比较自 2010 年起',position:'insideEndTop',color:muted,fontSize:10},lineStyle:{color:muted,type:'dashed',width:1},data:[{xAxis:'2010'}]}:undefined}));
      const plotHeight=height-118,last=spec.years.length-1;let cumulative=0;
      base.graphic=spec.series.map(s=>{const middle=cumulative+s.values[last]/2;cumulative+=s.values[last];return {type:'text',style:{x:width-215,y:58+(155-middle)/155*plotHeight,text:`${s.name}  ${s.values[last].toFixed(2)} 万英里\n占三类合计 ${s.shares[last].toFixed(1)}%`,fill:ink,font:'12px Microsoft YaHei',lineHeight:18,verticalAlign:'middle'}};});
      base.graphic.push({type:'text',style:{x:width-215,y:58+(155-spec.total[last])/155*plotHeight-15,text:`三类合计 ${spec.total[last].toFixed(2)} 万英里`,fill:ink,font:'12px Microsoft YaHei',verticalAlign:'bottom'}});
      return base;
    }
    if(spec.kind==='time_profiles') {
      const graphic=[],series=[],red='#9A2B2E',cyan='#B8D4D6';
      const txt=(x,y,text,size=14,color=ink)=>({type:'text',style:{x,y,text,fill:color,font:`${size}px Microsoft YaHei`,align:'center',lineHeight:23}});
      graphic.push(txt(width/2,14,'深红：伤亡报告    浅青：其余报告    每个圆表示该组全部报告',13,muted));
      spec.groups.forEach((period,i)=>{
        graphic.push(txt(width*(i*.5+.25),61,period+'收件',16));
        spec.series.forEach((part,j)=>{
          const r=part.rows[i],x=width*(i*.5+.135+j*.23),y=201;
          graphic.push(txt(x,108,part.name,15));
          graphic.push(txt(x,y-11,r.rate.toFixed(1)+'%',22,red));
          graphic.push(txt(x,280,`伤亡 ${r.k} / 全部 ${r.n} 份`,14));
          series.push({type:'pie',center:[x,y],radius:[45,66],startAngle:90,label:{show:false},
            selectedMode:false,emphasis:{disabled:true},data:[
              {name:'伤亡报告',value:r.k,itemStyle:{color:red},row:r,category:part.name,period},
              {name:'其余报告',value:r.n-r.k,itemStyle:{color:cyan},row:r,category:part.name,period}]});
        });
      });
      graphic.push({type:'line',shape:{x1:width/2,y1:53,x2:width/2,y2:313},style:{stroke:'#e2e8eb'}});
      return {...base,grid:undefined,graphic,series,tooltip:{confine:true,trigger:'item',formatter:p=>`${p.data.period} · ${p.data.category}<br>伤亡 ${p.data.row.k} 份<br>其余 ${p.data.row.n-p.data.row.k} 份<br>全部 ${p.data.row.n} 份`}};
    }
    if(spec.kind==='material_cells') {
      const graphic=[],series=[],red='#9A2B2E',cyan='#B8D4D6';
      const txt=(x,y,text,size=14,color=ink)=>({type:'text',style:{x,y,text,fill:color,font:`${size}px Microsoft YaHei`,align:'center',lineHeight:22}});
      graphic.push(txt(width/2,4,'深红：伤亡报告    浅青：其余报告    六个圆面积相同',13,muted));
      spec.groups.forEach((g,i)=>graphic.push(txt(width*(i+.5)/3,40,g,16)));
      spec.periods.forEach((g,j)=>graphic.push(txt(width/2,81+j*255,g+'收件',15)));
      spec.cells.forEach(c=>{
        const x=width*(c.row+.5)/3,y=189+c.column*255;
        series.push({type:'pie',center:[x,y],radius:[42,63],startAngle:90,label:{show:false},
          selectedMode:false,emphasis:{disabled:true},data:[{name:'伤亡报告',value:c.k,itemStyle:{color:red},cell:c},
          {name:'其余报告',value:c.n-c.k,itemStyle:{color:cyan},cell:c}]});
        graphic.push(txt(x,y-11,c.rate.toFixed(1)+'%',22,red));
        graphic.push(txt(x,y+78,`伤亡 ${c.k} / 全部 ${c.n} 份`,14));
      });
      graphic.push({type:'line',shape:{x1:25,y1:309,x2:width-25,y2:309},style:{stroke:'#e2e8eb'}});
      return {...base,grid:undefined,graphic,series,tooltip:{confine:true,trigger:'item',formatter:p=>{const c=p.data.cell;return `${spec.groups[c.row]} · ${spec.periods[c.column]}<br>伤亡 ${c.k} 份<br>其余 ${c.n-c.k} 份<br>全部 ${c.n} 份`;}}};
    }
    if(spec.kind==='paired_points') {
      base.grid={left:180,right:230,top:55,bottom:62};
      base.legend={top:4,left:180,selectedMode:false,textStyle:{color:ink},data:spec.series.map(s=>s.name)};
      base.xAxis={...valueAxis,max:60,interval:20,name:'伤亡报告占该组报告的比例（%）',nameLocation:'middle',nameGap:35};
      base.yAxis={type:'category',inverse:true,data:spec.groups,axisLine:{show:false},axisTick:{show:false},
        axisLabel:{color:ink,fontSize:12,margin:15}};
      base.tooltip={trigger:'item',confine:true,formatter:p=>{const d=p.value;return `${spec.groups[d[1]]} · ${p.seriesName}<br>伤亡 ${d[3]}/${d[2]} 份（${d[0].toFixed(1)}%）`;}};
      base.series=[{type:'custom',silent:true,data:spec.groups.map((_,i)=>[spec.series[0].rows[i].rate,spec.series[1].rows[i].rate,i]),
        renderItem:(params,api)=>{const a=api.coord([api.value(0),api.value(2)]),b=api.coord([api.value(1),api.value(2)]);
          return {type:'line',shape:{x1:a[0],y1:a[1]-9,x2:b[0],y2:b[1]+9},style:{stroke:'#C6D0D5',lineWidth:1.5}};}},
        ...spec.series.map((s,j)=>({type:'custom',name:s.name,itemStyle:{color:s.color},
          data:s.rows.map((r,i)=>[r.rate,i,r.n,r.k]),renderItem:(params,api)=>{
            const p=api.coord([api.value(0),api.value(1)]),y=p[1]+(j===0?-9:9);
            return {type:'group',children:[{type:'circle',shape:{cx:p[0],cy:y,r:4.5},style:{fill:s.color}},
              {type:'text',style:{x:width-205,y,text:`${s.name} ${api.value(0).toFixed(1)}%  ${api.value(3)}/${api.value(2)}`,
                fill:ink,font:'12px Microsoft YaHei',verticalAlign:'middle'}}]};}}))];
      return base;
    }
    return base;
  }
 function personnelDifference(spec,width){
 const red='#9A2B2E',cyan='#B8D4D6',gray='#8499B0';
 const colors=[red,'#B36B4E','#7E4B55',cyan];
 const decals=[null,null,{symbol:'circle',symbolSize:.7,dashArrayX:[2,4],dashArrayY:[3,4],color:'rgba(255,255,255,.8)'},null];
 const axis={type:'value',axisLabel:{color:muted},axisLine:{show:true,lineStyle:{color:'#BDCAD1'}},axisTick:{show:false},splitLine:{show:false},nameTextStyle:{color:ink,fontSize:12}};
 const legend={top:5,left:'center',selectedMode:false,data:spec.category_labels,textStyle:{color:ink,fontSize:12},itemWidth:22,itemHeight:13,itemGap:20};
 const base={animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei, sans-serif',color:ink}};
 const details=r=>`${r.location_name} · ${r.part_name}<br>全部 ${r.n} 份，伤亡 ${r.k} 份（${r.rate.toFixed(1)}%）<br>`+r.counts.map((n,j)=>`${spec.category_labels[j]}：${n} 份（${r.shares[j].toFixed(1)}%）`).join('<br>');

  const rows=spec.groups.map((name,i)=>{const a=spec.rows[2*i],b=spec.rows[2*i+1];return {name,a,b,values:a.shares.slice(0,3).map((v,j)=>b.shares[j]-v),total:b.rate-a.rate};});
  return {...base,legend:{...legend,data:[...spec.category_labels.slice(0,3),{name:'三项相加的总差',icon:'diamond'}]},tooltip:{trigger:'axis',axisPointer:{type:'shadow',axis:'y'},confine:true,formatter:items=>{const r=rows[items[0].dataIndex];return `${r.name} · 进户管 − 主管道<br>`+r.values.map((v,j)=>`${spec.category_labels[j]}：${v>0?'+':''}${v.toFixed(2)} 个百分点`).join('<br>')+`<br>合计 ${r.total.toFixed(2)} 个百分点<br>主管道伤亡 ${r.a.k}/${r.a.n} 份；进户管伤亡 ${r.b.k}/${r.b.n} 份`; }},
   grid:{left:200,right:210,top:75,bottom:64},xAxis:{...axis,min:-8,max:28,name:'进户管 − 主管道：人员后果比例差（百分点）',nameLocation:'middle',nameGap:34},
   yAxis:{type:'category',inverse:true,data:spec.groups,axisLabel:{color:ink,fontSize:12},axisLine:{show:false},axisTick:{show:false}},
   series:[...spec.category_labels.slice(0,3).map((name,j)=>({type:'bar',name,stack:'difference',barWidth:31,data:rows.map((r,i)=>({value:r.values[j],itemStyle:{opacity:i===3?.45:1}})),itemStyle:{color:colors[j],decal:decals[j],borderColor:'white',borderWidth:.5},
    label:{show:true,color:'white',position:'inside',formatter:p=>Math.abs(p.value)>=1.8?(p.value>0?'+':'')+p.value.toFixed(1):''},markLine:j===0?{silent:true,symbol:'none',label:{show:false},lineStyle:{color:gray,type:'solid',width:1},data:[{xAxis:0}]}:undefined})),
    {type:'scatter',name:'三项相加的总差',symbol:'diamond',symbolSize:13,symbolOffset:[0,24],data:rows.map((r,i)=>[r.total,i]),itemStyle:{color:'white',borderColor:ink,borderWidth:2},z:5},
    {type:'custom',silent:true,data:[[rows[1].values[0]+rows[1].values[2]/2,1]],renderItem:(p,api)=>{const q=api.coord([api.value(0),1]);return {type:'group',children:[{type:'line',shape:{x1:q[0],y1:q[1]-17,x2:q[0],y2:q[1]-29},style:{stroke:ink,lineWidth:.8}},{type:'text',style:{x:q[0],y:q[1]-33,text:'−1.3',align:'center',verticalAlign:'bottom',fill:ink,font:'12px Microsoft YaHei'}}]};}},
    {type:'custom',silent:true,data:rows.map((r,i)=>[r.total,i]),renderItem:(p,api)=>{const row=rows[api.value(1)],y=api.coord([0,api.value(1)])[1];return {type:'text',style:{x:width-195,y,text:`总差 ${row.total>0?'+':''}${row.total.toFixed(1)}\n进户管伤亡 ${row.b.k}/${row.b.n} 份\n主管道伤亡 ${row.a.k}/${row.a.n} 份`,fill:ink,font:'12px Microsoft YaHei',lineHeight:18,verticalAlign:'middle'}};}}]};
 }

  function outcomeRates(spec) {
    const p=spec.panels[0], red='#9A2B2E', cyan='#B8D4D6';
    const detail=i=>`${p.rows[i]}<br>全部报告：${spec.reports[i]} 份<br>伤亡报告：${spec.cases[i]} 份（${(100*spec.cases[i]/spec.reports[i]).toFixed(1)}%）<br>每万英里·年全部报告：${spec.total[i].toFixed(3)} 份<br>每万英里·年伤亡报告：${p.values[i].toFixed(3)} 份<br>伤亡报告率 95% 区间：${p.low[i].toFixed(3)}–${p.high[i].toFixed(3)}`;
    return {animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei, sans-serif'},
      legend:{top:6,left:190,data:['伤亡报告','其余报告',{name:'伤亡报告率区间',icon:'path://M0 0H2V3H22V0H24V8H22V5H2V8H0Z'}],selectedMode:false,itemWidth:16,itemHeight:11,
        formatter:name=>name==='伤亡报告率区间'?'伤亡报告率的 95% 区间':name,
        textStyle:{color:ink,fontSize:13},itemGap:28},
      tooltip:{trigger:'axis',axisPointer:{type:'shadow',axis:'y'},confine:true,
        formatter:items=>detail(items[0].dataIndex)},
      grid:{left:190,right:72,top:64,bottom:72},
      xAxis:{type:'value',min:0,max:1.6,interval:.4,name:'每万英里·年的报告数（份）',nameLocation:'middle',nameGap:36,
        nameTextStyle:{color:ink,fontSize:13},axisLabel:{color:muted,fontSize:12},axisTick:{show:false},
        axisLine:{show:true,lineStyle:{color:'#BDCAD1'}},splitLine:{lineStyle:{color:'#E6EBEE'}}},
      yAxis:{type:'category',inverse:true,data:p.rows,axisTick:{show:false},axisLine:{show:false},
        axisLabel:{color:ink,fontSize:13,lineHeight:22,margin:18,
          formatter:(name,i)=>`${name}\n伤亡 ${spec.cases[i]}/${spec.reports[i]} · ${(100*spec.cases[i]/spec.reports[i]).toFixed(1)}%`}},
      series:[
        {type:'bar',name:'伤亡报告',stack:'reports',barWidth:25,data:p.values,itemStyle:{color:red},emphasis:{disabled:true}},
        {type:'bar',name:'其余报告',stack:'reports',barWidth:25,data:spec.total.map((v,i)=>v-p.values[i]),
          itemStyle:{color:cyan},emphasis:{disabled:true},
          label:{show:true,position:'right',distance:10,color:muted,fontSize:13,formatter:item=>spec.total[item.dataIndex].toFixed(3)}},
        {type:'custom',name:'伤亡报告率区间',silent:true,z:4,itemStyle:{color:red},
          data:p.values.map((v,i)=>[p.low[i],p.high[i],i,v]),renderItem:(params,api)=>{
            const a=api.coord([api.value(0),api.value(2)]),b=api.coord([api.value(1),api.value(2)]),c=api.coord([api.value(3),api.value(2)]);
            const y=c[1]+25;
            return {type:'group',children:[
              {type:'line',shape:{x1:a[0],y1:y,x2:b[0],y2:y},style:{stroke:red,lineWidth:1.4}},
              ...[a,b].map(q=>({type:'line',shape:{x1:q[0],y1:y-4,x2:q[0],y2:y+4},style:{stroke:red,lineWidth:1.4}})),
              {type:'circle',shape:{cx:c[0],cy:y,r:3},style:{fill:red}},
              {type:'text',style:{x:c[0]+3,y:c[1]-21,text:api.value(3).toFixed(3),fill:red,font:'13px Microsoft YaHei',verticalAlign:'bottom'}}
            ]};
          }}
      ]};
  }
  function profiles(spec, width, height) {
    const top=70,bottom=65,left=44,matrixWidth=width*.53,cellWidth=matrixWidth/4;
    const rowHeight=(height-top-bottom)/8,plotLeft=left+matrixWidth+38,plotRight=75;
    const graphic=[];
    spec.columns.forEach((name,j)=>graphic.push({type:'text',style:{x:left+(j+.5)*cellWidth,y:28,
      text:name,fill:ink,font:'13px Microsoft YaHei',align:'center'}}));
    for(let i=0;i<8;i++)graphic.push({type:'text',style:{x:15,y:top+(i+.5)*rowHeight,text:String(i+1),
      fill:ink,font:'13px Microsoft YaHei',verticalAlign:'middle'}});
    graphic.push({type:'text',style:{x:8,y:28,text:'组别',fill:ink,font:'12px Microsoft YaHei'}});
    for(const c of spec.cells) {
      const x=left+c.column*cellWidth,y=top+c.row*rowHeight;
      const label=c.label.replace('室外表具／调压装置','室外表具／\n调压装置').replace('公用设施通行权区域','公用设施\n通行权区域');
      graphic.push({type:'rect',shape:{x:x+2,y:y+3,width:cellWidth-4,height:rowHeight-6},style:{fill:'#F3F6F7'}});
      graphic.push({type:'text',style:{x:x+cellWidth/2,y:y+rowHeight/2,text:`${label}\n${(c.share*100).toFixed(1)}%`,
        fill:ink,font:'12px Microsoft YaHei',lineHeight:18,align:'center',verticalAlign:'middle'}});
    }
    graphic.push({type:'text',style:{x:width-65,y:28,text:'伤亡／全部',fill:muted,font:'11px Microsoft YaHei'}});
    return {animation:false,backgroundColor:'#fff',graphic,
      textStyle:{fontFamily:'Microsoft YaHei, sans-serif'},
      tooltip:{trigger:'item',confine:true,formatter:p=>{const d=p.data;
        return `第 ${d[2]+1} 组 · ${p.seriesName}<br>伤亡 ${d[5]}/${d[4]} 份<br>观察比例 ${d[3].toFixed(1)}%`;}},
      legend:{left:plotLeft,top:20,selectedMode:false,data:['较早期','较晚期'],textStyle:{fontSize:12,color:ink}},
      grid:{left:plotLeft,right:plotRight,top,bottom},
      xAxis:{type:'value',min:0,max:100,interval:25,name:'伤亡报告占组内报告的比例（%）',nameLocation:'middle',nameGap:32,
        nameTextStyle:{fontSize:12,color:ink},axisLabel:{color:muted},axisLine:{show:true,lineStyle:{color:'#BDCAD1'}},splitLine:{lineStyle:{color:'#E6EBEE'}}},
      yAxis:{type:'category',inverse:true,data:[1,2,3,4,5,6,7,8],axisLabel:{show:false},axisLine:{show:false},axisTick:{show:false}},
      series:[['early',-.15,'#638794','较早期'],['late',.15,'#9A2B2E','较晚期']].map(([period,offset,color,name])=>({
        type:'custom',name,itemStyle:{color},data:spec.periods[period].map((r,i)=>[100*r.wilson_low,100*r.wilson_high,i,100*r.precision,r.n,r.cases]),
        renderItem:(params,api)=>{const c=api.coord([api.value(3),api.value(2)]);
          const y=c[1]+offset*rowHeight;
          return {type:'group',children:[
            {type:'circle',shape:{cx:c[0],cy:y,r:3.5},style:{fill:color}},
            {type:'text',style:{x:width-65,y,text:`${api.value(5)}/${api.value(4)}`,fill:color,font:'12px Microsoft YaHei',verticalAlign:'middle'}}
          ]};}
      }))};
  }
  function option(spec, width, height, key) {
    if(spec.kind==='personnel_difference') return personnelDifference(spec,width);
    if(['history','time_profiles','paired_points','material_cells'].includes(spec.kind)) return contextOption(spec,width,height);
    if(spec.kind==='profiles') return profiles(spec,width,height);
    if(spec.kind==='outcome_rates') return outcomeRates(spec);
    const n = spec.panels.length, left = n === 1 ? 170 : 112;
    const gap = 46, right = 20, panelWidth = (width - left - right - gap*(n-1))/n;
    const out = {animation:false, backgroundColor:'#fff', textStyle:{fontFamily:'Microsoft YaHei, sans-serif'},
      tooltip:{trigger:'item', confine:true, formatter:p=>{
        const r=p.data.row, f=p.data.panel;
        if(r === undefined || !f) return '';
        let text=`${f.rows[r]}<br>${f.label}：${f.values[r].toFixed(f.decimals)}`;
        if(f.low) text+=`<br>95% 区间：${f.low[r].toFixed(f.decimals)}–${f.high[r].toFixed(f.decimals)}`;
        return text;
      }}, grid:[],xAxis:[],yAxis:[],series:[]};
    spec.panels.forEach((p,i)=>{
      out.grid.push({left:left+i*(panelWidth+gap),width:panelWidth,top:35,bottom:72});
      out.xAxis.push({gridIndex:i,type:'value',min:p.minimum??0,max:p.maximum,splitNumber:4,name:p.label,
        nameLocation:'middle',nameGap:36,nameTextStyle:{fontSize:12,color:ink},
        axisLabel:{fontSize:11,color:muted},axisLine:{show:true,lineStyle:{color:'#BDCAD1'}},
        axisTick:{show:false},splitLine:{lineStyle:{color:'#E6EBEE'}}});
      out.yAxis.push({gridIndex:i,type:'category',inverse:true,data:p.rows,
        axisLabel:{show:i===0,fontSize:13,color:ink,margin:13},axisLine:{show:false},axisTick:{show:false}});
      if(p.low) out.series.push({type:'custom',xAxisIndex:i,yAxisIndex:i,silent:true,z:2,
        data:p.values.map((v,r)=>[p.low[r],p.high[r],r]),renderItem:(params,api)=>{
          const a=api.coord([api.value(0),api.value(2)]),b=api.coord([api.value(1),api.value(2)]);
          return {type:'group',children:[{type:'line',shape:{x1:a[0],y1:a[1],x2:b[0],y2:b[1]}},
            {type:'line',shape:{x1:a[0],y1:a[1]-5,x2:a[0],y2:a[1]+5}},
            {type:'line',shape:{x1:b[0],y1:b[1]-5,x2:b[0],y2:b[1]+5}}].map(x=>({...x,style:{stroke:p.color,lineWidth:1.5}}))};
        }});
      out.series.push({type:p.low?'scatter':'bar',xAxisIndex:i,yAxisIndex:i,symbolSize:9,barWidth:22,z:3,
        itemStyle:{color:p.color},emphasis:{disabled:true},
        data:p.values.map((v,r)=>({value:p.low?[v,r]:v,row:r,panel:p})),
        markLine:p.reference===null?undefined:{symbol:'none',silent:true,label:{show:false},
          lineStyle:{color:'#8499B0',type:'dashed'},data:[{xAxis:p.reference}]}});
      out.series.push({type:'scatter',xAxisIndex:i,yAxisIndex:i,symbolSize:0,silent:true,z:4,
        data:p.values.map((v,r)=>({value:[p.maximum*.97,r],row:r})),
        label:{show:true,position:key==='feature_ablation'?'left':'top',distance:key==='feature_ablation'?3:13,color:ink,fontSize:13,
          formatter:item=>p.values[item.data.row].toFixed(p.decimals)}});
    });
    return out;
  }
  document.querySelectorAll('.evidence-chart').forEach(element=>{
    element.style.display='block';
    const spec=window.CDT502_EVIDENCE.figures[element.dataset.key];
    const chart=echarts.init(element,null,{renderer:'canvas'}),figure=element.closest('figure');
    const draw=()=>{chart.resize();chart.setOption(option(spec,element.clientWidth,element.clientHeight,element.dataset.key),{notMerge:true});};
    draw(); figure.classList.add('chart-ready');
    const button=figure.querySelector('.chart-download'); button.hidden=false;
    button.addEventListener('click',()=>{
      const a=document.createElement('a'); a.download=element.dataset.key+'.png';
      a.href=chart.getDataURL({type:'png',pixelRatio:3,backgroundColor:'#fff'}); a.click();
    });
    const observer=new ResizeObserver(()=>{if(chart.getWidth()!==element.clientWidth)draw();});
    observer.observe(element);instances.push({chart,observer});
  });
})();
