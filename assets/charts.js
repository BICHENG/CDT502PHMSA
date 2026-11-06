'use strict';

(() => {
  const source = window.CDT502_CHART_DATA;
  if (!window.echarts || !source) return;
  const color = { ...source.colors, total: '#8499b0', ink: '#253b50', muted: '#66788a', grid: '#e8edf2' };
  const outcome = ['有死亡或因伤住院', '未记录死亡或因伤住院'];
  const labels = { paired: '数量与区间', stacked: '百分比构成', sankey: '桑基图' };
  const captions = {
    paired: '左侧条形表示各类全部报告数；右侧圆点表示伤亡比例，横线为 Wilson 95% 置信区间。右侧数字依次为比例、伤亡报告数／该类全部报告数。',
    stacked: '每行都是该类的全部报告（100%），深色部分表示伤亡比例。横线为 Wilson 95% 置信区间，右侧保留比例和原始计数。',
    sankey: '每类报告按伤亡结果分成两条流带，宽度表示报告份数。类别旁同时标出伤亡份数和伤亡比例。'
  };
  const charts = new Map();
  const number = n => n.toLocaleString('zh-CN');
  const percent = n => `${n.toFixed(1)}%`;
  const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[c]);
  const detail = row => `<strong>${escape(row.label)}</strong><br/>全部报告：${number(row.n)} 份<br/>伤亡报告：${number(row.k)} 份<br/>未记录死亡或因伤住院：${number(row.other)} 份<br/>伤亡比例：${row.k} ÷ ${row.n} = <b>${percent(row.rate)}</b><br/>Wilson 95% 置信区间：${percent(row.low)}—${percent(row.high)}`;

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
    const height = mode === 'sankey' ? Math.max(440, 140+rows.length*64) : Math.max(440, 140+rows.length*48);
    entry.element.style.height = `${height}px`;
    entry.chart.resize();
    const option = mode === 'sankey' ? sankey(rows) : cartesian(rows, entry.element.clientWidth, mode);
    entry.chart.setOption(option, { notMerge: true });
    entry.figure.dataset.chartMode = mode;
    entry.figure.querySelector('.chart-caption').textContent = captions[mode];
    entry.element.setAttribute('aria-label', `${labels[mode]}。${rows.map(r => `${r.label}：${r.k}/${r.n}，${percent(r.rate)}`).join('；')}`);
  }

  for (const element of document.querySelectorAll('.echart')) {
    const key = element.dataset.key;
    const figure = element.closest('figure');
    element.style.display = 'block';
    const entry = { key, element, figure, chart: echarts.init(element, null, { renderer: 'canvas' }) };
    charts.set(key, entry);
    render(entry);
    figure.classList.add('chart-ready');
    figure.querySelector('.chart-download').hidden = false;
  }

  for (const button of document.querySelectorAll('[data-download-chart]')) {
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
