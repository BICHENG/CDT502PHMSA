(function(){'use strict';
const red='#982f3f',cyan='#c5dfe2',amber='#a76936',noFire='#d9e1e6',ink='#173241',fmt=(n,d=1)=>Number(n).toFixed(d);
function init(target){const host=typeof target==='string'?document.querySelector(target):target;host.classList.add('excavation-visual');return host;}
window.renderExcavationFlow=function(target,D){
 const host=init(target);host.innerHTML='<p class="ev-scope"></p><div class="ev-chart" role="img" aria-label="开挖报告的材料、燃气点燃与伤亡联合分类"></div><p class="ev-legend"></p><p class="ev-caption"></p>';
 const q=s=>host.querySelector(s),chart=echarts.init(q('.ev-chart'));const onlyIgnited=false;
 function draw(){
  const paths=D.paths.filter(r=>(!onlyIgnited||r.ignited===1)&&r.reports>0),nodes=[],links=[];
  const sum=(material,ignited,casualty)=>paths.filter(r=>r.material===material&&(ignited===undefined||r.ignited===ignited)&&(casualty===undefined||r.casualty===casualty)).reduce((s,r)=>s+r.reports,0);
  for(const m of D.materials){const n=sum(m);nodes.push({name:m,depth:0,value:n,label:{position:'left',formatter:`${D.materialNames[m]}\n${n} 份`},itemStyle:{color:'#6a8797'},material:m,kind:'material'});}
  if(!onlyIgnited)for(const m of D.materials)for(const fire of [1,0]){
   const name=m+'|'+fire,n=sum(m,fire);nodes.push({name,depth:1,value:n,material:m,fire,kind:'ignition',label:{position:'left',formatter:`${D.materialNames[m]}·${fire?'点燃':'未点燃'}\n${n} 份`},itemStyle:{color:fire?amber:noFire}});
   links.push({source:m,target:name,value:n,material:m,fire,kind:'ignition',lineStyle:{color:fire?amber:noFire,opacity:fire?.7:.8}});
  }
  for(const r of paths){const name=r.material+'|'+r.ignited+'|'+r.casualty;
   nodes.push({name,depth:onlyIgnited?1:2,value:r.reports,material:r.material,fire:r.ignited,casualty:r.casualty,kind:'outcome',label:{position:'right',formatter:`${D.materialNames[r.material]}·${r.ignited?'点燃':'未点燃'}\n${r.casualty?'伤亡':'其余'} ${r.reports} 份`},itemStyle:{color:r.casualty?red:cyan}});
   links.push({source:onlyIgnited?r.material:r.material+'|'+r.ignited,target:name,value:r.reports,material:r.material,fire:r.ignited,casualty:r.casualty,kind:'outcome',lineStyle:{color:r.casualty?red:cyan,opacity:r.casualty?.84:.74}});
  }
  q('.ev-scope').textContent=onlyIgnited?'120份均报告燃气点燃，其中钢20份、塑料100份；按各材料的伤亡记录分类。':'2010—2024年，钢196份、塑料195份，共391份开挖归因报告；依次按燃气点燃与伤亡记录分类。';
  q('.ev-legend').innerHTML=(onlyIgnited?'':`<i style="background:${amber}"></i>报告燃气点燃<i style="background:${noFire}"></i>未报告燃气点燃　`)+`<i style="background:${red}"></i>伤亡报告<i style="background:${cyan}"></i>其余报告`;
  q('.ev-caption').textContent=onlyIgnited?'点燃记录中的伤亡报告为钢6／20、塑料32／100。线宽统一表示报告份数。':'每条完整路径保留材料身份，节点分别列出钢与塑料。钢的未点燃记录中伤亡为0份；塑料的未点燃记录中伤亡为3份。线宽表示报告份数。';
  const graphics=onlyIgnited?[{type:'text',left:88,top:0,style:{text:'已报告燃气点燃',font:'12px "Microsoft YaHei"',fill:'#526a77'}},{type:'text',right:150,top:0,style:{text:'伤亡记录',font:'12px "Microsoft YaHei"',fill:'#526a77'}}]:[{type:'text',left:70,top:0,style:{text:'材料与全部报告',font:'12px "Microsoft YaHei"',fill:'#526a77'}},{type:'text',left:'42%',top:0,style:{text:'燃气点燃记录',font:'12px "Microsoft YaHei"',fill:'#526a77'}},{type:'text',right:135,top:0,style:{text:'伤亡记录',font:'12px "Microsoft YaHei"',fill:'#526a77'}}];
  chart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei',color:ink},graphic:graphics,tooltip:{confine:true,formatter:p=>{const r=p.data;let s=`${D.materialNames[r.material]}`;if(r.fire!==undefined)s+=' · '+(r.fire?'报告燃气点燃':'未报告燃气点燃');if(r.casualty!==undefined)s+=' · '+(r.casualty?'伤亡报告':'其余报告');return s+'<br>'+r.value+' 份';}},series:[{type:'sankey',left:100,right:160,top:35,bottom:10,nodeWidth:12,nodeGap:27,nodeAlign:'left',layoutIterations:0,draggable:false,label:{fontSize:12,lineHeight:16,color:ink},data:nodes,links,emphasis:{focus:'adjacency'},lineStyle:{curveness:.45}}]},{notMerge:true});
  chart.__excavationState={onlyIgnited,paths,total:paths.reduce((s,r)=>s+r.reports,0),leftTotal:links.filter(l=>!l.source.includes('|')).reduce((s,l)=>s+l.value,0),outcomeTotal:links.filter(l=>l.kind==='outcome').reduce((s,l)=>s+l.value,0)};
 }
 const ro=new ResizeObserver(()=>chart.resize());ro.observe(host);draw();return{chart,destroy:()=>{ro.disconnect();chart.dispose();host.replaceChildren();}};
};
window.renderPressureDiameter=function(target,D){
 const host=init(target);host.innerHTML='<p class="ev-scope">正常运行压力满足1＜压力≤60 psig的287份开挖归因报告，钢101份、塑料186份。psig表示相对大气压的压力单位。</p><div class="ev-key"><span data-ev-size>圆面积与报告份数成正比</span><span>每格数字：点燃份数／全部份数 · 点燃比例</span></div><p class="ev-legend"><i style="background:'+amber+'"></i>报告燃气点燃<i style="background:'+noFire+'"></i>未报告燃气点燃</p><div class="ev-chart" role="img" aria-label="共同压力范围内按材料和管径分组的报告数量与燃气点燃构成"></div><p class="ev-caption">管径由左侧分组标签表示。钢有64／101份位于>4英寸组，塑料有135／186份位于≤4英寸两组；各管径档的点燃比例可逐行比较。</p>';
 const q=s=>host.querySelector(s),chart=echarts.init(q('.ev-chart'));const equal=false;
 function draw(){
  const w=chart.getWidth(),xs=[w*.35,w*.74],ys=[90,245,400],maxN=Math.max(...D.cells.map(r=>r.reports)),maxRadius=55,graphics=[],series=[];
  for(let i=0;i<2;i++)graphics.push({type:'text',x:xs[i],y:10,style:{text:D.materialNames[D.materials[i]]+' · '+D.pressureTotals.find(r=>r.material===D.materials[i]).reports+' 份',align:'center',font:'600 14px "Microsoft YaHei"',fill:ink}});
  for(let band=0;band<3;band++){
   graphics.push({type:'text',x:10,y:ys[band],style:{text:D.diameterLabels[band],verticalAlign:'middle',font:'13px "Microsoft YaHei"',fill:ink}});
   for(let i=0;i<2;i++){
    const r=D.cells.find(x=>x.material===D.materials[i]&&x.band===band),radius=equal?maxRadius:maxRadius*Math.sqrt(r.reports/maxN);
    series.push({type:'pie',name:D.materialNames[r.material]+' · '+D.diameterLabels[band],center:[xs[i],ys[band]],radius,animation:false,clockwise:true,startAngle:90,avoidLabelOverlap:false,label:{show:false},labelLine:{show:false},emphasis:{scale:false},itemStyle:{borderColor:'#fff',borderWidth:1},data:[{name:'报告燃气点燃',value:r.ignited,itemStyle:{color:amber},cell:r},{name:'未报告燃气点燃',value:r.reports-r.ignited,itemStyle:{color:noFire},cell:r}]});
    graphics.push({type:'text',x:xs[i],y:ys[band]+70,style:{text:`${r.ignited}／${r.reports} · ${fmt(100*r.proportion)}%`,align:'center',font:'14px "Microsoft YaHei"',fill:ink}});
   }
  }
  q('[data-ev-size]').textContent=equal?'各圆同尺寸，扇形比较点燃比例':'圆面积与报告份数成正比';
  chart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei',color:ink},tooltip:{confine:true,formatter:p=>{const r=p.data.cell;return `${D.materialNames[r.material]} · ${D.diameterLabels[r.band]}<br>${p.name}：${p.value} 份<br>点燃 ${r.ignited}／${r.reports}，${fmt(100*r.proportion)}%<br>来自 ${r.operators} 个运营商编号`;}},graphic:graphics,series},{notMerge:true});
  chart.__pressureDiameterState={equal,total:D.cells.reduce((s,r)=>s+r.reports,0),cells:D.cells,radii:series.map(s=>s.radius),maxN,maxRadius};
 }
 const ro=new ResizeObserver(()=>{chart.resize();draw();});ro.observe(host);draw();return{chart,destroy:()=>{ro.disconnect();chart.dispose();host.replaceChildren();}};
};
})();
