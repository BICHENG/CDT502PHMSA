(function () {
  'use strict';
  const colors = ['#286083', '#739fb9', '#c7dce8', '#f0f1ef', '#efdbc5', '#ce9760', '#965420'];
  const materials = ['CAST/WROUGHT IRON', 'STEEL', 'PLASTIC'];
  const shortNames = ['铸铁／锻铁', '钢', '塑料'];
  const fmt = (n, digits = 0) => Number(n).toLocaleString('en-US', {maximumFractionDigits: digits});
  const signed = (n, digits = 0) => `${n < 0 ? '−' : n > 0 ? '+' : ''}${fmt(Math.abs(n), digits)}`;
  const direction = n => n < 0 ? '净减少' : n > 0 ? '净增加' : '无变化';
  const bin = n => n === 0 ? 3 : (n < 0 ? 2 - (Math.abs(n) < 1000 ? 0 : Math.abs(n) <= 5000 ? 1 : 2) : 4 + (n < 1000 ? 0 : n <= 5000 ? 1 : 2));
  const scale = colors.flatMap((color, i) => [[i / colors.length, color], [(i + 1) / colors.length, color]]);
  const nameFor = (data, state) => `${data.stateNames[state].zh} ${state}`;

  window.renderIntegratedMaterialMap = function (target, data, geometry) {
    const host = typeof target === 'string' ? document.querySelector(target) : target;
    if (!host || !data || !geometry || !window.Plotly) throw new Error('Missing map data, geometry or Plotly.');
    const rows = new Map(data.rows.map(row => [`${row.state}|${row.material}`, row]));
    let currentState = 'NJ';
    let ready = false;
    const topNames = data.topFiveIron.map(state => `<button type="button" data-state="${state}">${nameFor(data, state)}</button>`).join('');
    host.classList.add('net-map');
    host.innerHTML = `
      <p class="net-map-intro">2010至2024年，塑料主管道在52个州或地区均增加；铁管在35个地区减少。钢管在45个地区减少、6个地区增加。</p>
      <p class="net-mobile-note">三种材料并排显示，窄屏可横向滚动。</p>
      <div class="net-scroll"><div class="net-grid">${materials.map((material, i) => {
        const n = data.national[material];
        const counts = [`${n.decrease_regions}个地区减少`, `${n.increase_regions}个地区增加`, `${n.unchanged_regions}个地区不变`].filter((_, j) => [n.decrease_regions, n.increase_regions, n.unchanged_regions][j] > 0);
        return `<section class="net-panel"><h3>${shortNames[i]}</h3><p class="net-total ${n.net_change < 0 ? 'negative' : 'positive'}"><strong>${signed(n.net_change)}</strong> 英里<span>全国${direction(n.net_change)}</span></p><p class="net-stock">2024年在用 ${fmt(n.miles_2024)} 英里</p><div class="net-chart" data-material="${material}" role="img" aria-label="${shortNames[i]}，2010至2024年52个州或地区主管道里程净变化"></div><p class="net-counts">${counts.join(' · ')}</p></section>`;
      }).join('')}</div></div>
      <div class="net-legend" aria-label="各州净变化共用分档，单位英里"><span class="net-legend-label">各州净变化<br>英里</span>${['减少 >5,000', '减少 1,000至5,000', '减少 <1,000', '不变', '增加 <1,000', '增加 1,000至5,000', '增加 >5,000'].map((label, i) => `<span><i style="background:${colors[i]}"></i>${label}</span>`).join('')}</div>
      <p class="net-five-note">2024年铁管的 ${(100 * data.topFiveIronShare).toFixed(1)}% 位于以下五州。点州名或悬停地图，可同时查看该州三种材料。</p>
      <div class="net-state-buttons" aria-label="2024年现存铁管最多的五州">${topNames}</div>
      <div class="net-readout" aria-live="polite" aria-atomic="true"><h4></h4><table><thead><tr><th>材料</th><th>2010年在用</th><th>2024年在用</th><th>净变化</th></tr></thead><tbody></tbody></table></div>
      <p class="net-boundary">净变化是两年年末在用长度之差，不能据此确认某段铁管是否换成塑料。阿拉斯加、夏威夷和波多黎各移位显示。</p>`;
    const charts = [...host.querySelectorAll('.net-chart')];
    const geos = [false, true].map(pr => ({...geometry, features: geometry.features.filter(f => (f.properties.name === 'Puerto Rico') === pr)}));

    function updateReadout(state) {
      currentState = state;
      host.dataset.selectedState = state;
      host.querySelector('.net-readout h4').textContent = `${nameFor(data, state)} · 主管道里程，英里`;
      host.querySelector('.net-readout tbody').innerHTML = materials.map((material, i) => {
        const row = rows.get(`${state}|${material}`);
        return `<tr><th>${shortNames[i]}</th><td>${fmt(row.miles_2010, 1)}</td><td>${fmt(row.miles_2024, 1)}</td><td class="${row.net_change < 0 ? 'negative' : row.net_change > 0 ? 'positive' : ''}">${signed(row.net_change, 1)}</td></tr>`;
      }).join('');
      host.querySelectorAll('[data-state]').forEach(button => button.setAttribute('aria-pressed', button.dataset.state === state ? 'true' : 'false'));
    }

    async function selectState(state) {
      if (!data.stateNames[state]) return;
      updateReadout(state);
      if (!ready) return;
      await Promise.all(charts.map(chart => Plotly.restyle(chart, {
        'marker.line.color': [chart.data[0].customdata.map(row => row[1] === state ? '#1a3440' : '#ffffff')],
        'marker.line.width': [chart.data[0].customdata.map(row => row[1] === state ? 2.1 : .65)]
      }, [0])));
      await Promise.all(charts.map(chart => Plotly.restyle(chart, {
        'marker.line.color': [state === 'PR' ? '#1a3440' : '#ffffff'],
        'marker.line.width': [state === 'PR' ? 2.1 : .65]
      }, [1])));
    }

    function trace(material, pr) {
      const selected = data.rows.filter(row => row.material === material && (row.state === 'PR') === pr);
      return {
        type: 'choropleth', geo: pr ? 'geo2' : 'geo', geojson: geos[Number(pr)],
        featureidkey: 'properties.name', locationmode: 'geojson-id',
        locations: selected.map(row => row.state_en), z: selected.map(row => bin(row.net_change)),
        customdata: selected.map(row => [row.state_zh, row.state, fmt(row.miles_2010, 1), fmt(row.miles_2024, 1), signed(row.net_change, 1), data.materialNames[material]]),
        zmin: -.5, zmax: 6.5, colorscale: scale, showscale: false,
        marker: {line: {color: selected.map(row => row.state === currentState ? '#1a3440' : '#ffffff'), width: selected.map(row => row.state === currentState ? 2.1 : .65)}},
        hovertemplate: '<b>%{customdata[0]} %{customdata[1]}</b><br>%{customdata[5]}<br>2010年：%{customdata[2]} 英里<br>2024年：%{customdata[3]} 英里<br>净变化：%{customdata[4]} 英里<extra></extra>'
      };
    }

    const promise = Promise.all(charts.map(async (chart, i) => {
      const traces = [trace(materials[i], false), trace(materials[i], true)];
      if (i === 0) {
        traces.push({type: 'scattergeo', geo: 'geo', mode: 'text', lon: [-85.5, -76.3, -78.5], lat: [44.7, 43.2, 40.8], text: ['MI', 'NY', 'PA'], textfont: {size: 10, color: '#102d3b'}, hoverinfo: 'skip', showlegend: false});
        traces.push({type: 'scattergeo', geo: 'geo', mode: 'lines', lon: [-71.5, -68.6, null, -74.5, -69.5], lat: [42.3, 43.6, null, 40.2, 39.0], line: {color: '#536977', width: .7}, hoverinfo: 'skip', showlegend: false});
        traces.push({type: 'scattergeo', geo: 'geo', mode: 'text', lon: [-68.4, -69.3], lat: [43.6, 39.0], text: ['MA', 'NJ'], textposition: 'middle right', textfont: {size: 10, color: '#102d3b'}, hoverinfo: 'skip', showlegend: false});
      }
      const layout = {height: 245, margin: {l: 0, r: 0, t: 0, b: 0}, paper_bgcolor: '#ffffff', showlegend: false,
        font: {family: 'Arial, Microsoft YaHei, sans-serif', color: '#173241'},
        hoverlabel: {bgcolor: '#ffffff', bordercolor: '#b7c8d1', font: {size: 13}},
        geo: {domain: {x: [0, 1], y: [.10, 1]}, visible: false, projection: {type: 'albers usa'}, showland: false, showlakes: false, showrivers: false, showcoastlines: false, showcountries: false},
        geo2: {domain: {x: [.84, .96], y: [.03, .10]}, visible: false, fitbounds: 'locations', projection: {type: 'equirectangular'}, showland: false, showcoastlines: false}};
      await Plotly.newPlot(chart, traces, layout, {displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false});
      const onHover = event => {
        const state = event.points?.[0]?.customdata?.[1];
        if (state && state !== currentState) selectState(state);
      };
      chart.on('plotly_hover', onHover);
      chart.on('plotly_click', onHover);
    })).then(() => { ready = true; host.dataset.ready = 'true'; });
    host.querySelectorAll('[data-state]').forEach(button => {
      button.addEventListener('click', () => selectState(button.dataset.state));
      button.addEventListener('focus', () => selectState(button.dataset.state));
    });
    updateReadout(currentState);
    return {ready: promise, charts, selectState, getState: () => currentState};
  };

  window.renderFiveStateAppendix = function (target, data) {
    const host = document.querySelector(target);
    host.innerHTML = `<table class="appendix-table"><thead><tr><th>州</th><th>铁管净变化</th><th>钢管净变化</th><th>塑料管净变化</th><th>2024年铁管在用</th></tr></thead><tbody>${data.topFiveIron.map(state => {
      const selected = materials.map(material => data.rows.find(row => row.state === state && row.material === material));
      return `<tr><th>${nameFor(data, state)}</th>${selected.map(row => `<td>${signed(row.net_change, 1)}</td>`).join('')}<td>${fmt(selected[0].miles_2024, 1)}</td></tr>`;
    }).join('')}</tbody></table>`;
  };
})();
