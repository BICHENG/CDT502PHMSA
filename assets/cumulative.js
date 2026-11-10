(function(){'use strict';
const ink='#173241',meta={constant:{name:'常数参照',color:'#939ba2',dash:[4,4],symbol:'circle'},part:{name:'部件规则',color:'#426f98',dash:'solid',symbol:'circle'},logit:{name:'逻辑回归',color:'#a67737',dash:[9,3],symbol:'diamond'},rf:{name:'随机森林',color:'#377b73',dash:'solid',symbol:'rect'}};
window.renderCumulative=function(target,D){
 const host=typeof target==='string'?document.querySelector(target):target;
 const k=53;
 host.classList.add('cumulative-compare');
 host.innerHTML='<p class="cu-scope"></p><div class="cu-layout"><div class="cu-chart" role="img" aria-label="四种方法的完整累计曲线，选取报告数从0至264；53份为固定阅读示例"></div><aside class="cu-readout"><p class="cu-selected"></p><div class="cu-values"></div><p class="cu-value-unit">其中伤亡报告的期望份数</p></aside></div><p class="cu-ties">各方法按分数从高到低选取报告。同分报告获得相同入选机会，图中显示平均可识别的伤亡报告份数，因此读数可以出现小数。悬浮可查看任意选取数量的读数。</p>';
 const q=selector=>host.querySelector(selector),chart=echarts.init(q('.cu-chart'));
 q('.cu-scope').textContent='2022年起收到的'+D.n+'份既有报告，其中'+D.cas+'份伴随伤亡。本图使用已知伤亡结果，对四种方法作回顾比较。';
 q('.cu-selected').innerHTML='各方法共同选取 <strong>'+k+' 份</strong><span>占全部报告的 '+(100*k/D.n).toFixed(1)+'%</span>';
 q('.cu-values').innerHTML=D.series.map(series=>'<div class="cu-value"><span><i class="cu-line cu-'+series.id+'" style="--cu-color:'+meta[series.id].color+'"></i>'+meta[series.id].name+'</span><strong>'+series.hits[k].toFixed(2)+'</strong></div>').join('');
 const series=D.series.map((item,i)=>({id:item.id,name:meta[item.id].name,type:'line',data:D.x.map((x,j)=>[x,item.hits[j]]),smooth:false,showSymbol:false,symbol:meta[item.id].symbol,animation:false,lineStyle:{color:meta[item.id].color,width:item.id==='constant'?1.8:2.5,type:meta[item.id].dash},itemStyle:{color:meta[item.id].color},z:item.id==='constant'?1:3,emphasis:{disabled:true},markLine:i===0?{silent:true,symbol:['none','none'],label:{show:false},lineStyle:{color:'#bac7cd',width:1.2,type:'dashed'},data:[{xAxis:k}]}:undefined}));
 chart.setOption({animation:false,backgroundColor:'#fff',textStyle:{fontFamily:'Microsoft YaHei',color:ink},grid:{left:66,right:22,top:67,bottom:61},legend:{top:5,left:65,itemWidth:27,itemHeight:8,itemGap:19,selectedMode:false,textStyle:{fontSize:12,color:ink},data:D.series.map(item=>meta[item.id].name)},
  tooltip:{trigger:'axis',confine:true,axisPointer:{type:'line',snap:true,lineStyle:{color:'#6d8794',width:1}},formatter:items=>{
   const x=Math.round(items[0].value[0]);
   return '<strong>各方法选取 '+x+'／'+D.n+' 份</strong><br>其中伤亡报告的期望份数<br>'+D.series.map(item=>meta[item.id].name+'：'+item.hits[x].toFixed(2)).join('<br>');
  }},
  xAxis:{type:'value',min:0,max:D.n,interval:50,name:'选取报告数（份）',nameLocation:'middle',nameGap:36,nameTextStyle:{fontSize:13,color:ink},axisLabel:{fontSize:12,color:'#4e6674',showMinLabel:true,showMaxLabel:true},axisLine:{lineStyle:{color:'#a9bbc4'}},axisTick:{show:false},splitLine:{show:false}},
  yAxis:{type:'value',min:0,max:D.cas,interval:10,name:'其中伤亡报告数（期望份数）',nameLocation:'end',nameTextStyle:{fontSize:12,color:ink,align:'left',padding:[0,0,8,-50]},axisLabel:{fontSize:12,color:'#4e6674',showMinLabel:true,showMaxLabel:true},axisLine:{show:false},axisTick:{show:false},splitLine:{lineStyle:{color:'#e8edef'}}},series},{notMerge:true});
 chart.__cumulativeState={k,values:D.series.map(item=>({id:item.id,name:meta[item.id].name,hits:item.hits[k]})),pointsPerMethod:series.map(item=>item.data.length),xMax:D.n,yMax:D.cas};
 const observer=new ResizeObserver(()=>chart.resize());observer.observe(host);
 return{chart,getState:()=>chart.__cumulativeState,destroy:()=>{observer.disconnect();chart.dispose();host.replaceChildren();}};
};
})();
