(function(){'use strict';
const ink='#173241',keys=['pubOnly','staffOnly','both','none','unk'];
const names={pubOnly:'仅一般公众',staffOnly:'仅工作人员等',both:'两类均有伤亡',none:'未记录死亡或住院伤害',unk:'伤亡人员身份未明'};
const colors={pubOnly:'#47799B',staffOnly:'#B89048',both:'#DFCDA6',none:'#DCE8E9',unk:'#8e969c'};
const decals={both:{symbol:'rect',color:'#47799B',backgroundColor:'#DFCDA6',dashArrayX:[1,0],dashArrayY:[3,3],rotation:-Math.PI/4},unk:{symbol:'rect',dashArrayX:[2,3],dashArrayY:[2,3],color:'rgba(255,255,255,.45)'}};
const pct=(k,n)=>n?(100*k/n).toFixed(1)+'%':'—';
window.renderClusterCompare=function(target,D){
 const host=typeof target==='string'?document.querySelector(target):target;
 const groups=D.default.groups.map(id=>D.groups.find(group=>group.id===id));
 const panels=D.periods.flatMap(period=>groups.map(group=>({period,group:group.id,sample:group[period.id].main})));
 const active=keys.filter(key=>key!=='unk'||panels.some(panel=>panel.sample.unk>0));
 function context(sample){return [...new Set(sample.mix.map(row=>row.loc))].map(location=>(D.labels[location]||location)+' · '+sample.mix.filter(row=>row.loc===location).sort((a,b)=>b.n-a.n).map(row=>(D.labels[row.mat]||row.mat)+' '+row.n+'份').join('、')).join('；');}
 host.classList.add('cluster-compare');
 host.innerHTML='<p class="cc-scope">早期第1组162份中有136份主管道，第3组141份中有36份主管道。下图比较这些主管道及近年来归入两组的主管道；四环面积相同，中心为报告份数。</p><div class="cc-period-heads">'+D.periods.map(period=>'<h3>'+period.label+'</h3>').join('')+'</div><div class="cc-heads">'+panels.map(panel=>'<div><strong>'+(panel.group===1?'公共地点':'私人地点')+' · 主管道</strong><span>'+context(panel.sample)+'</span></div>').join('')+'</div><div class="cc-chart" role="img" aria-label="早期第1与第3组主管道136和36份，晚期20和9份，按互斥人员后果分类"></div><table class="cc-table"><thead><tr><th scope="col">人员后果</th>'+panels.map(panel=>'<th scope="col">'+(panel.period.id==='early'?'早期':'晚期')+' · '+(panel.group===1?'公共地点':'私人地点')+'<br>'+panel.sample.n+'份报告</th>').join('')+'</tr></thead><tbody>'+active.map(key=>'<tr><th scope="row"><i class="cc-swatch cc-'+key+'" style="--cc-color:'+colors[key]+'"></i>'+names[key]+'</th>'+panels.map(panel=>'<td>'+panel.sample[key]+'／'+panel.sample.n+' <span>'+pct(panel.sample[key],panel.sample.n)+'</span></td>').join('')+'</tr>').join('')+'</tbody></table><p class="cc-reading"></p><p class="cc-caption"></p>';
 const q=selector=>host.querySelector(selector),chart=echarts.init(q('.cc-chart'));
 const inclusive=panels.map(panel=>panel.sample.pubOnly+panel.sample.both);
 q('.cc-reading').textContent='涉及一般公众的报告包含“两类均有伤亡”：早期两组分别为'+inclusive[0]+'／'+panels[0].sample.n+'（'+pct(inclusive[0],panels[0].sample.n)+'）和'+inclusive[1]+'／'+panels[1].sample.n+'（'+pct(inclusive[1],panels[1].sample.n)+'）；晚期分别为'+inclusive[2]+'／'+panels[2].sample.n+'（'+pct(inclusive[2],panels[2].sample.n)+'）和'+inclusive[3]+'／'+panels[3].sample.n+'（'+pct(inclusive[3],panels[3].sample.n)+'）。';
 q('.cc-caption').textContent=(active.includes('unk')?'五':'四')+'类人员后果互斥，每份报告计一次。工作人员等包括运营商员工、运营商承包商人员、应急响应人员和其他工作人员。聚类依据部件、材料、地点与地区等级，仅用早期报告拟合中心；晚期报告分配至既有中心。伤亡及人员身份用于分组后的描述。';
 function draw(){
  const width=chart.getWidth(),radius=Math.min(88,width/8-18),centerY=110;
  const series=panels.map((panel,i)=>({type:'pie',name:panel.period.label+'第'+panel.group+'组主管道',center:[width*(i+.5)/4,centerY],radius:[radius*.6,radius],startAngle:90,clockwise:true,animation:false,label:{show:false},labelLine:{show:false},emphasis:{scale:false},minAngle:0,avoidLabelOverlap:false,itemStyle:{borderColor:'#fff',borderWidth:1},data:active.map(key=>({name:names[key],value:panel.sample[key],key,n:panel.sample.n,group:panel.group,period:panel.period.label,itemStyle:{color:colors[key],decal:decals[key]}}))}));
  const graphic=panels.map((panel,i)=>({type:'group',x:width*(i+.5)/4,y:centerY,children:[{type:'text',style:{text:String(panel.sample.n),x:0,y:-8,align:'center',verticalAlign:'middle',font:'600 26px "Microsoft YaHei"',fill:ink}},{type:'text',style:{text:'份报告',x:0,y:18,align:'center',verticalAlign:'middle',font:'12px "Microsoft YaHei"',fill:'#57717e'}}]}));
  chart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei',color:ink},tooltip:{confine:true,formatter:point=>point.data.period+'<br>第'+point.data.group+'组中的主管道<br>'+point.name+'：'+point.value+'／'+point.data.n+'份（'+pct(point.value,point.data.n)+'）'},graphic,series},{notMerge:true});
  chart.__clusterCompareState={periods:D.periods.map(period=>period.id),groupIds:groups.map(group=>group.id),samples:panels.map(panel=>panel.sample),active,totals:series.map(item=>item.data.reduce((sum,row)=>sum+row.value,0)),inclusivePublic:inclusive,seriesCenters:series.map(item=>item.center),radii:series.map(item=>item.radius)};
 }
 const observer=new ResizeObserver(()=>{chart.resize();draw();});observer.observe(host);draw();
 return{chart,getState:()=>chart.__clusterCompareState,destroy:()=>{observer.disconnect();chart.dispose();host.replaceChildren();}};
};
})();
