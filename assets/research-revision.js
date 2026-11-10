(() => {
 'use strict';
 const data=window.RESEARCH_REVISION;if(!data||!window.echarts)return;
 if(document.getElementById('material-map'))window.currentMaterialMap=renderMaterialMap('#material-map',MATERIAL_MAP_DATA,USA_GEO);
 if(document.getElementById('material-causes'))window.currentMaterialCauses=renderMaterialCause('#material-causes',MATERIAL_CAUSE_DATA);
 if(document.getElementById('excavation-flow'))window.currentExcavationFlow=renderExcavationFlow('#excavation-flow',EXCAVATION_VISUAL_DATA);
 if(document.getElementById('pressure-diameter'))window.currentPressureDiameter=renderPressureDiameter('#pressure-diameter',EXCAVATION_VISUAL_DATA);
 if(document.getElementById('cluster-compare'))window.currentClusterCompare=renderClusterCompare('#cluster-compare',data.clusters);
 if(document.getElementById('cumulative-hits'))window.currentCumulative=renderCumulative('#cumulative-hits',data.cumulative);
 const ink='#173241',muted='#526974',red='#9A2B2E',cyan='#B8D4D6';
 const axis=(labels,inverse=false)=>({type:'category',data:labels,inverse,axisLine:{show:false},axisTick:{show:false},axisLabel:{color:ink,fontSize:13,margin:15}});
 const base={animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei, sans-serif',color:ink},tooltip:{confine:true}};
 for(const element of document.querySelectorAll('.revision-chart')){
  const key=element.dataset.key,chart=echarts.init(element,null,{renderer:'canvas'});
  function render(){
   if(key==='association'){
    const width=element.clientWidth,gap=24,col=(width-2*gap)/3;
    const fields=[['SYSTEM_PART_INVOLVED','部件'],['MATERIAL_INVOLVED','材料'],['LOCATION_TYPE','地点']];
    const graphic=[],series=[],baseline=369/1550;
    const text=(x,y,t,size=13,color=ink,weight='normal')=>({type:'text',style:{x,y,text:t,fill:color,font:`${weight} ${size}px Microsoft YaHei`,lineHeight:21}});
    graphic.push(text(0,4,'全体伤亡比例  369 / 1,550 = 23.8%',15,ink,'bold'));
    graphic.push(text(0,31,'各类的参考份数按同一比例计算；圆面积相同，比较伤亡构成。',12,muted));
    graphic.push({type:'rect',shape:{x:width-215,y:8,width:12,height:12},style:{fill:red}});
    graphic.push(text(width-195,4,'伤亡',12));
    graphic.push({type:'rect',shape:{x:width-128,y:8,width:12,height:12},style:{fill:cyan}});
    graphic.push(text(width-108,4,'其余报告',12));
    fields.forEach(([field,name],j)=>{
      const spec=data.association[field],x=j*(col+gap),rows=spec.cells.filter(c=>c.column===0);
      graphic.push(text(x,77,name,18,ink,'bold'));
      graphic.push({type:'line',shape:{x1:x,y1:110,x2:x+col,y2:110},style:{stroke:'#dbe4e8'}});
      rows.forEach((c,i)=>{
        const y=133+i*72,cy=y+30,label=spec.labels[i].replace('Farm tap 计量／调压装置','农用支线计量／调压装置');
        series.push({type:'pie',center:[x+25,cy],radius:[16,25],clockwise:true,startAngle:90,
          selectedMode:false,silent:false,emphasis:{disabled:true},label:{show:false},labelLine:{show:false},
          data:[{value:c.actual,name:'伤亡',itemStyle:{color:red},cell:c,category:label},
                {value:c.n-c.actual,name:'其余报告',itemStyle:{color:cyan},cell:c,category:label}]});
        graphic.push(text(x+64,y,label,13,ink,'bold'));
        graphic.push(text(x+64,y+24,`${c.actual} / ${c.n} 份 · ${(100*c.actual/c.n).toFixed(1)}%`,13,red));
        const delta=c.actual-c.expected;
        graphic.push(text(x+64,y+45,`参考 ${c.expected.toFixed(1)} 份 · ${delta>=0?'多':'少'} ${Math.abs(delta).toFixed(1)}`,12,muted));
      });
      const fy=133+rows.length*72+9;
      graphic.push({type:'line',shape:{x1:x,y1:fy,x2:x+col,y2:fy},style:{stroke:'#dbe4e8'}});
      graphic.push(text(x,fy+13,`χ² = ${spec.chi2.toFixed(3)}  ·  自由度 ${spec.df}`,13));
      graphic.push(text(x,fy+39,`校正 p = ${spec.p.toFixed(4)}`,14,ink,'bold'));
    });
    element.style.height='940px';chart.resize();
    chart.setOption({...base,graphic,series,tooltip:{confine:true,formatter:p=>{
      const c=p.data.cell;return `${p.data.category}<br>全部 ${c.n} 份<br>伤亡 ${c.actual} 份（${(100*c.actual/c.n).toFixed(1)}%）<br>其余 ${c.n-c.actual} 份<br>按全体23.8%计算的参考伤亡份数 ${c.expected.toFixed(1)}`;
    }}},{notMerge:true});
   }
   if(key==='locations'){
    const width=element.clientWidth,graphic=[],series=[],cells=data.locations['全部时期'];
    const blue='#47799B',gold='#B89048',mixed='#B7BBA9',other='#DCE8E9';
    const txt=(x,y,text,size=13,color=ink,align='left')=>({type:'text',style:{x,y,text,fill:color,font:`${size}px Microsoft YaHei`,lineHeight:21,align}});
    [['仅公众',blue],['仅工作人员等',gold],['两类均有伤亡',mixed],['其余报告',other]].forEach(([label,color],i)=>{
      const x=18+i*width/4;graphic.push({type:'rect',shape:{x,y:10,width:14,height:14},style:{fill:i===2?'#DFCDA6':color}});
      if(i===2)[0,4,8].forEach(d=>graphic.push({type:'line',shape:{x1:x+d,y1:24,x2:x+14,y2:10+d},style:{stroke:blue,lineWidth:2}}));
      graphic.push(txt(x+22,6,label));
    });
    const order=[1,0,2,3];
    order.forEach((r,i)=>{
      const top=56+i*190,label=data.location_labels[r].replace('公用设施通行权 / 地役权区域','公用设施通行权区域');
      graphic.push(txt(6,top,label,15));
      graphic.push({type:'line',shape:{x1:6,y1:top+27,x2:width-6,y2:top+27},style:{stroke:'#e2e8eb'}});
      [0,1].forEach(j=>{
        const c=cells.find(c=>c.row===r&&c.column===j),cx=width*(j*.5+.075),cy=top+99,tx=cx+71;
        const values=[c.public-c.both,c.worker-c.both,c.both,c.n-c.k];
        series.push({type:'pie',center:[cx,cy],radius:48,startAngle:90,selectedMode:false,label:{show:false},emphasis:{disabled:true},
          data:values.map((v,k)=>({name:['仅公众','仅工作人员等','两类均有伤亡','其余报告'][k],value:v,cell:c,location:label,
            itemStyle:{color:[blue,gold,mixed,other][k],...(k===2?{decal:{symbol:'rect',color:blue,backgroundColor:'#DFCDA6',dashArrayX:[1,0],dashArrayY:[3,3],rotation:-Math.PI/4}}:{})}}))});
        graphic.push(txt(tx,top+44,j?'进户管':'主管道',15));
        graphic.push(txt(tx,top+70,`伤亡 ${(100*c.k/c.n).toFixed(1)}% · ${c.k}/${c.n} 份`,14,red));
        graphic.push(txt(tx,top+99,`仅公众 ${values[0]} · 仅工作人员 ${values[1]}`,12));
        graphic.push(txt(tx,top+122,`两类均有 ${c.both} · 其余 ${values[3]} 份`,12,muted));
      });
    });
    element.style.height='825px';chart.resize();
    chart.setOption({...base,graphic,series,tooltip:{confine:true,formatter:p=>{const c=p.data.cell;return `${p.data.location} · ${c.column?'进户管':'主管道'}<br>${p.name}：${p.value} 份<br>全部 ${c.n} 份，伤亡 ${c.k} 份<br>涉及公众 ${c.public} 份；涉及工作人员等 ${c.worker} 份<br>两类交集 ${c.both} 份（已单列）`;}}},{notMerge:true});
   }
   if(key==='material_consequences'){
    const width=element.clientWidth,graphic=[],series=[],max=Math.max(...data.materials.map(r=>r.frequency));
    const txt=(x,y,text,size=14,color=ink)=>({type:'text',style:{x,y,text,fill:color,font:`${size}px Microsoft YaHei`,align:'center',lineHeight:23}});
    graphic.push(txt(width/2,7,'圆面积：每万英里·年的全部事故报告数    深红部分：其中的伤亡报告',13,muted));
    data.materials.forEach((r,i)=>{
      const x=width*(i+.5)/3,cy=285,radius=96*Math.sqrt(r.frequency/max);
      graphic.push(txt(x,54,r.label,17));
      graphic.push(txt(x,90,`原始记录  ${r.n} 份 · 伤亡 ${r.k} 份`,14));
      graphic.push(txt(x,118,`E＝${r.exposure.toLocaleString('en-US',{minimumFractionDigits:3,maximumFractionDigits:3})} 英里·年`,13,muted));
      graphic.push(txt(x,157,'↓ 换算为相同长度与年数',12,muted));
      series.push({type:'pie',center:[x,cy],radius,startAngle:90,label:{show:false},selectedMode:false,emphasis:{disabled:true},
        data:[{value:r.k,name:'伤亡报告',itemStyle:{color:red},row:r},{value:r.n-r.k,name:'其余报告',itemStyle:{color:cyan},row:r}]});
      graphic.push(txt(x,410,`全部事故  ${r.frequency.toFixed(3)}`,16));
      graphic.push(txt(x,442,`其中伤亡  ${r.harm_rate.toFixed(3)}`,18,red));
      graphic.push(txt(x,474,'单位：份／万英里·年',12,muted));
      graphic.push(txt(x,509,`伤亡占该材料事故的 ${r.proportion.toFixed(1)}%`,13));
    });
    element.style.height='558px';chart.resize();
    chart.setOption({...base,graphic,series,tooltip:{confine:true,formatter:p=>{const r=p.data.row;return `${r.label}<br>伤亡 ${r.k}／全部 ${r.n} 份<br>累计 ${r.exposure.toLocaleString()} 英里·年<br>每万英里·年全部事故 ${r.frequency.toFixed(3)} 份<br>其中伤亡 ${r.harm_rate.toFixed(3)} 份<br>伤亡报告率95%区间 ${r.low.toFixed(3)} 至 ${r.high.toFixed(3)}`;}}},{notMerge:true});
   }
  }
  if(element.clientWidth) render();
  const disclosure=element.closest('details');
  if(disclosure) disclosure.addEventListener('toggle',()=>{if(disclosure.open){chart.resize();render();}});
  element.closest('figure').querySelectorAll('select,input').forEach(s=>s.addEventListener('change',render));new ResizeObserver(()=>chart.resize()).observe(element);
 }
})();
