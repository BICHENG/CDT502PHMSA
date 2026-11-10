/* Python supplies actual annual PHMSA inventories and Plotly frames. */
(function () {
  'use strict';
  const font = '-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  const materials = ['CAST/WROUGHT IRON', 'STEEL', 'PLASTIC'];
  const colors = ['#f1f5f6', '#d0e5e8', '#a7cbd2', '#7eafba', '#4e8a9e', '#2e657f', '#163f5c'];
  const marks = ['#96563e', '#7d8994', '#c1cdcf'];
  const format = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString('en-US', {maximumFractionDigits:digits});
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const styles = `
    .material-map{color:#173241;font:14px/1.7 ${font};max-width:100%}.material-map *{box-sizing:border-box}
    .material-map:focus-visible{outline:2px solid #477a87;outline-offset:6px}
    .material-map .mm-time{display:flex;align-items:baseline;justify-content:space-between;gap:8px 22px;flex-wrap:wrap;border-bottom:1px solid #dce5e8;padding-bottom:12px;margin-bottom:20px}
    .material-map .mm-year{font-size:29px;line-height:1.2;font-weight:650;font-variant-numeric:tabular-nums;letter-spacing:-.03em}
    .material-map .mm-phase{font-size:13px;color:#526974;margin-left:10px}.material-map .mm-years{font-size:13px;color:#526974;word-spacing:6px}
    .material-map .mm-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
    .material-map .mm-panel{min-width:0;margin:0}.material-map .mm-heading{display:flex;align-items:center;gap:8px;margin:0;font-size:17px;line-height:1.45;font-weight:600}
    .material-map .mm-mark{display:inline-block;flex:none;width:14px;height:14px;border-radius:2px;background:var(--material-color)}
    .material-map .mm-steel{background:repeating-linear-gradient(0deg,#617681 0,#617681 1px,#9aabb3 1px,#9aabb3 2px)}
    .material-map .mm-total{font-size:13px;color:#526974;margin:7px 0 0;font-variant-numeric:tabular-nums;white-space:nowrap}.material-map .mm-total strong{font-size:18px;font-weight:600;color:#173241}
    .material-map .mm-chart{height:245px;width:100%;min-width:0;margin-top:7px}.material-map .modebar{display:none!important}
    .material-map .mm-scale{font-size:12px;color:#365563;margin:13px 0 7px}.material-map .mm-legend{display:flex;flex-wrap:wrap;gap:6px 16px;list-style:none;padding:0;margin:0;font-size:11px;color:#405b69;font-variant-numeric:tabular-nums}
    .material-map .mm-legend li{display:flex;align-items:center;gap:5px;white-space:nowrap}.material-map .mm-swatch{width:14px;height:11px;display:inline-block;border:1px solid #c5d2d7;flex:none}
    .material-map .mm-summary{font-size:14px;line-height:1.85;margin:17px 0 0}.material-map .mm-note{font-size:12px;line-height:1.8;color:#607581;margin:10px 0 0}
    @media(max-width:680px){.material-map .mm-grid{grid-template-columns:1fr;gap:22px}.material-map .mm-panel+.mm-panel{border-top:1px solid #e4ebed;padding-top:17px}.material-map .mm-years{font-size:12px;word-spacing:2px}.material-map .mm-summary{font-size:13px}}
    @media print{.material-map .mm-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.material-map .mm-panel+.mm-panel{border:0;padding:0}.material-map .mm-heading{font-size:11px}.material-map .mm-mark{width:10px;height:10px}.material-map .mm-total{font-size:9px}.material-map .mm-total strong{font-size:12px}.material-map .mm-chart{height:165px}.material-map .svg-container,.material-map svg.main-svg{width:100%!important;height:100%!important}.material-map .mm-summary{font-size:10px}.material-map .mm-note{font-size:8px}.material-map .mm-legend{font-size:8px;gap:5px 10px}.material-map .mm-time{padding-bottom:8px;margin-bottom:12px}.material-map .mm-year{font-size:22px}.material-map .hoverlayer{display:none!important}.material-map{break-inside:avoid;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  `;

  window.renderMaterialMap = function (target, data, geography, options = {}) {
    const host = typeof target === 'string' ? document.querySelector(target) : target;
    const animation = options.frames || window.MATERIAL_MAP_FRAMES;
    const figures = options.figures || window.MATERIAL_MAP_PLOTLY;
    if (!host || !data || !window.Plotly || !animation || !figures) throw new Error('Material map needs the local Plotly bundle, geographic assets and Python-generated frames/figures.');
    const frames = animation.frames;
    const years = animation.observed_years;
    const lastIndex = frames.length - 1;
    if (frames.some(frame => frame.kind !== 'observed') || figures.length !== 3 || figures.some(figure => figure.frames.length !== frames.length)) throw new Error('Material map requires matching annual observations for all materials.');
    if (!document.getElementById('material-map-style')) {
      const style = document.createElement('style');
      style.id = 'material-map-style'; style.textContent = styles; document.head.appendChild(style);
    }
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let index = motion.matches || options.autoplay === false ? lastIndex : 0;
    if (years.includes(options.year)) index = frames.findIndex(frame => frame.year === options.year);
    let renderedIndex = -1, visible = false, hovered = false, focused = false, printing = false;
    let explicitFrame = options.autoplay === false, timer = null, destroyed = false, initialized = false;
    let beforePrintIndex = null, width = host.clientWidth;
    host.classList.add('material-map'); host.tabIndex = 0; host.setAttribute('role', 'group');
    host.setAttribute('aria-label', `铁、钢、塑料主管道里程。${years[0]}至${years.at(-1)}年，每帧对应实际年度记录，循环播放；打印使用最后一年。`);
    host.innerHTML = `<div class="mm-time"><div><strong class="mm-year"></strong><span class="mm-phase"></span></div><span class="mm-years">${years[0]} → ${years.at(-1)} · 逐年实测</span></div><div class="mm-grid">${materials.map((material,i)=>`<section class="mm-panel"><h3 class="mm-heading"><span class="mm-mark ${i===1?'mm-steel':''}" style="--material-color:${marks[i]}" aria-hidden="true"></span>${escape(data.materialNames[material])}</h3><p class="mm-total"></p><div class="mm-chart" role="img"></div></section>`).join('')}</div><p class="mm-scale">各州／地区该材料里程，英里 · 三图与全部帧共用分档色阶</p><ul class="mm-legend">${data.mileageScale.map((piece,i)=>`<li><span class="mm-swatch" style="background:${colors[i]}" aria-hidden="true"></span>${escape(piece.label)}</li>`).join('')}<li><span class="mm-swatch" style="background:#a7afb5" aria-hidden="true"></span>资料缺失</li></ul><p class="mm-summary"></p><p class="mm-note">各帧对应实际年报。阿拉斯加、夏威夷和波多黎各移位显示。</p>`;
    const panels = [...host.querySelectorAll('.mm-panel')];
    const charts = panels.map(panel=>panel.querySelector('.mm-chart'));
    const counts = years.map(year=>data.national.find(row=>row.year===year&&row.material===materials[0]).states_with_positive_miles);
    const top = data.topFive.find(row=>row.year===2024&&row.material===materials[0]);
    host.querySelector('.mm-summary').textContent = `仍在使用铁主管道的地区由${years[0]}年的${counts[0]}个减少至2024年的${counts.at(-1)}个。2024年约三分之二的铁管里程集中在${top.states.map(state=>data.stateNames[state].zh).join('、')}五州。`;
    const fitSvg=chart=>chart.querySelectorAll('svg.main-svg').forEach(svg=>svg.setAttribute('viewBox',`0 0 ${chart._fullLayout.width} ${chart._fullLayout.height}`));

    function labels(frame) {
      host.querySelector('.mm-year').textContent = frame.label;
      host.querySelector('.mm-phase').textContent = '年末在用主管道';
      panels.forEach((panel,i)=>{
        panel.querySelector('.mm-total').innerHTML = `合计 <strong>${format(frame.panels[i].national.miles)}</strong> 英里`;
        charts[i].setAttribute('aria-label',`${frame.label}，年末记录，${data.materialNames[materials[i]]}主管道里程，52个州或地区。`);
      });
    }
    async function render() {
      const target = index, frame = frames[target];
      labels(frame);
      await Promise.all(charts.map(chart=>Plotly.animate(chart,[String(target)],{transition:{duration:0},frame:{duration:0,redraw:true},mode:'immediate'})));
      if (destroyed || target !== index) return;
      charts.forEach(fitSvg);
      renderedIndex = target;
      host.dataset.frame = target;
      const state = getState();
      if (options.onChange) options.onChange(state);
      host.dispatchEvent(new CustomEvent('materialmapframe',{detail:state}));
    }
    function schedule() {
      clearTimeout(timer); timer = null;
      if (!initialized || destroyed || !visible || focused || document.hidden || printing || explicitFrame || motion.matches) return;
      timer = setTimeout(async()=>{timer=null;index=(index+1)%frames.length;await render();schedule();},frames[index].duration_ms);
    }
    function getState() {
      const frame = frames[index];
      return {index,renderedIndex,year:frame.year,kind:frame.kind,fromYear:frame.from_year,toYear:frame.to_year,
        fraction:frame.fraction,frameCount:frames.length,materials:[...materials],playing:timer!==null};
    }
    labels(frames[index]);
    const ready = Promise.all(charts.map(async(chart,i)=>{
      const figure = figures[i];
      const initial = figure.data.map((trace,j)=>({...trace,...figure.frames[index].data[j]}));
      await Plotly.newPlot(chart,initial,{...figure.layout,font:{...figure.layout.font,family:font}},{displayModeBar:false,responsive:false,scrollZoom:false});
      await Plotly.addFrames(chart,figure.frames);
    })).then(async()=>{if(destroyed)return;initialized=true;await render();schedule();});
    const enter=()=>{hovered=true;schedule();}, leave=()=>{hovered=false;schedule();};
    const focus=()=>{focused=host.matches(':focus-visible');schedule();};
    const blur=event=>{if(!host.contains(event.relatedTarget)){focused=false;schedule();}};
    const visibility=()=>schedule();
    const reduce=async()=>{if(motion.matches){index=lastIndex;await ready;await render();}schedule();};
    const resizeCharts=()=>Promise.all(charts.map(chart=>Plotly.relayout(chart,{width:chart.clientWidth,height:chart.clientHeight}).then(()=>fitSvg(chart))));
    const beforePrint=()=>{
      if(printing)return;
      beforePrintIndex=index;printing=true;index=lastIndex;labels(frames[lastIndex]);schedule();
      charts.forEach((chart,i)=>{
        Plotly.restyle(chart,{z:figures[i].frames[lastIndex].data.map(trace=>trace.z),customdata:figures[i].frames[lastIndex].data.map(trace=>trace.customdata)});
      });
      resizeCharts();
      renderedIndex=lastIndex;host.dataset.frame=lastIndex;
    };
    const afterPrint=async()=>{if(!printing)return;printing=false;index=beforePrintIndex;await render();resizeCharts();schedule();};
    const resize=new ResizeObserver(()=>{if(initialized&&width!==host.clientWidth){width=host.clientWidth;resizeCharts();}});
    resize.observe(host);
    const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;schedule();});intersection.observe(host);
    host.addEventListener('pointerenter',enter);host.addEventListener('pointerleave',leave);host.addEventListener('focusin',focus);host.addEventListener('focusout',blur);
    document.addEventListener('visibilitychange',visibility);motion.addEventListener('change',reduce);window.addEventListener('beforeprint',beforePrint);window.addEventListener('afterprint',afterPrint);
    return {chart:charts[0],charts,ready,getState,
      async setState(next){
        const selected=Number.isInteger(next.frameIndex)?next.frameIndex:frames.findIndex(frame=>frame.year===next.year);
        if(selected<0||selected>=frames.length)return;
        explicitFrame=true;index=selected;schedule();await ready;await render();
      },
      destroy(){destroyed=true;clearTimeout(timer);resize.disconnect();intersection.disconnect();host.removeEventListener('pointerenter',enter);host.removeEventListener('pointerleave',leave);host.removeEventListener('focusin',focus);host.removeEventListener('focusout',blur);document.removeEventListener('visibilitychange',visibility);motion.removeEventListener('change',reduce);window.removeEventListener('beforeprint',beforePrint);window.removeEventListener('afterprint',afterPrint);charts.forEach(chart=>Plotly.purge(chart));host.replaceChildren();}
    };
  };
})();
