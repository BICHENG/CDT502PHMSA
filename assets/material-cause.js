(function(){'use strict';
window.renderMaterialCause=function(target,D){
 const host=typeof target==='string'?document.querySelector(target):target;
 if(!host||!D||!window.echarts)throw new Error('Material cause data and ECharts are required.');
 const ink='#173241',muted='#526974',red='#9A2B2E',cyan='#B8D4D6';
 host.classList.add('material-cause');
 host.innerHTML='<div class="mc-chart" role="img" aria-label="三种材料全部八类事故原因的报告数、伤亡份数和比例"></div>';
 const el=host.querySelector('.mc-chart');el.style.height='795px';const chart=echarts.init(el);
 const causes=['EXCAVATION DAMAGE','INCORRECT OPERATION','NATURAL FORCE DAMAGE','PIPE, WELD, OR JOINT FAILURE','CORROSION FAILURE','OTHER OUTSIDE FORCE DAMAGE','EQUIPMENT FAILURE','OTHER INCIDENT CAUSE'];
 function draw(){
   const width=el.clientWidth,left=170,col=(width-left)/3,graphic=[],series=[],max=Math.max(...D.rows.map(r=>r.reports));
   const text=(x,y,t,size=13,color=ink,align='left')=>({type:'text',style:{x,y,text:t,fill:color,font:`${size}px Microsoft YaHei`,lineHeight:21,align}});
   graphic.push(text(0,0,'圆面积＝该材料、该原因的报告数；深红扇形＝其中的伤亡报告',13,muted));
   D.materials.forEach((m,j)=>{
     const x=left+(j+.5)*col,total=D.totals.find(r=>r.material===m);
     graphic.push(text(x,44,D.materialNames[m],16,ink,'center'));
     graphic.push(text(x,72,`全部 ${total.reports} 份 · 伤亡 ${total.casualty_reports} 份`,12,muted,'center'));
   });
   causes.forEach((cause,i)=>{
     const y=148+i*82,label=cause==='PIPE, WELD, OR JOINT FAILURE'?'管道、焊缝​\n或接头失效':D.causeNames[cause];
     graphic.push(text(0,y-(label.includes('\n')?20:10),label,14));
     graphic.push({type:'line',shape:{x1:0,y1:y+41,x2:width,y2:y+41},style:{stroke:'#eef1f3'}});
     D.materials.forEach((m,j)=>{
       const r=D.rows.find(r=>r.material===m&&r.cause===cause),x=left+j*col+42,tx=x+49;
       if(r.reports){
         series.push({type:'pie',center:[x,y],radius:35*Math.sqrt(r.reports/max),startAngle:90,label:{show:false},selectedMode:false,emphasis:{disabled:true},
           data:[{value:r.casualty_reports,name:'伤亡报告',itemStyle:{color:red},row:r},
                 {value:r.reports-r.casualty_reports,name:'其余报告',itemStyle:{color:cyan},row:r}]});
         graphic.push(text(tx,y-23,`伤亡 ${r.casualty_reports} / 全部 ${r.reports}`,13));
         graphic.push(text(tx,y+1,`${(100*r.casualty_reports/r.reports).toFixed(1)}%`,14,red));
       }else{
         graphic.push({type:'circle',shape:{cx:x,cy:y,r:3},style:{fill:'transparent',stroke:'#b7c5ca',lineWidth:1}});
         graphic.push(text(tx,y-10,'0 份报告',13,muted));
       }
     });
   });
   chart.resize();chart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei',color:ink},graphic,series,
     tooltip:{confine:true,formatter:p=>{const r=p.data.row;return `${D.materialNames[r.material]} · ${D.causeNames[r.cause]}<br>全部 ${r.reports} 份<br>伤亡 ${r.casualty_reports} 份<br>其余 ${r.reports-r.casualty_reports} 份<br>伤亡比例 ${(100*r.casualty_reports/r.reports).toFixed(1)}%`;}}},{notMerge:true});
 }
 let w=0;const ro=new ResizeObserver(()=>{if(el.clientWidth!==w){w=el.clientWidth;draw();}});ro.observe(host);draw();
 return {chart,getState:()=>({view:'all-causes',reports:693,casualty_reports:141}),destroy:()=>{ro.disconnect();chart.dispose();host.replaceChildren();}};
};
})();
