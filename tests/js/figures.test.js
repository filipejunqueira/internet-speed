// Tests for the comparison charts: what ends up in the plotly specification, not what it
// looks like on screen.
//
// The two runs below are hand-built and small enough to check on paper — four probes a
// target, summary figures written out rather than derived — so every expected number here
// is a literal somebody can follow. Between them they carry the awkward cases: a target
// that is silent in both runs, one that is silent in only one of them, and a run with a
// probe that never came back.

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  histogramFigure, overviewFigure, penaltyFigure, themeRoles, timelineFigure
} from '../../src/pingme/site/figures.js'

// The block render_web.explorer_tokens() writes into the page, values and all.
const TOKENS = {
  runSlots: { light: ['#2a78d6', '#eb6834', '#1baf7a'], dark: ['#3987e5', '#d95926', '#199e70'] },
  chrome: {
    light: { surface: '#fcfcfb', page: '#f9f9f7', ink: '#0b0b0b', ink2: '#52514e',
      muted: '#898781', grid: '#e1e0d9', axis: '#c3c2b7', border: 'rgba(11,11,11,0.10)' },
    dark: { surface: '#1a1a19', page: '#0d0d0d', ink: '#ffffff', ink2: '#c3c2b7',
      muted: '#898781', grid: '#2c2c2a', axis: '#383835', border: 'rgba(255,255,255,0.10)' }
  },
  status: { good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b' },
  targetOrder: ['router', 'isp-hop', 'london', 'madrid', 'us-east', 'sao-paulo'],
  thresholds: { lossWarn: 1.0, lossCrit: 5.0, penaltyWarn: 50.0, penaltyCrit: 200.0,
    burstWarn: 2, burstCrit: 5 },
  intervalS: 0.2,
  maxRuns: 3,
  font: 'system-ui, sans-serif'
}

const ROLES = ['run0', 'run1', 'run2', 'lost', 'muted']

/** An address that answered, with its four round trips and the summary written out. */
function answered({ min, median, p95, p99, idleP95, busyP95, ms, lost = [] }) {
  return {
    ip: '203.0.113.1', kind: 'relay', error: null, silent: false,
    all: { sent: 4 + lost.length, received: 4, loss_pct: lost.length ? 20 : 0, min_ms: min,
      median_ms: median, mean_ms: median, p95_ms: p95, p99_ms: p99, max_ms: p99,
      stdev_ms: 5, jitter_ms: 3 },
    idle: { p95_ms: idleP95 },
    busy: { p95_ms: busyP95 },
    loss: lost.length
      ? { lost, longest_burst_probes: 1, longest_burst_s: 0.2, longest_burst_at_s: lost[0][1] }
      : { lost: [], longest_burst_probes: 0, longest_burst_s: 0, longest_burst_at_s: null },
    samples: ms.map((value, i) => [i + 1, value, i * 0.2, i < 2 ? 'idle' : 'download'])
  }
}

/** An address set to ignore probes: nothing came back, and none of that counts as loss. */
function silent() {
  return {
    ip: '203.0.113.99', kind: 'relay', error: null, silent: true,
    all: { sent: 20, received: 0, loss_pct: null, min_ms: null, median_ms: null, mean_ms: null,
      p95_ms: null, p99_ms: null, max_ms: null, stdev_ms: null, jitter_ms: null },
    idle: { p95_ms: null }, busy: { p95_ms: null }, loss: null, samples: []
  }
}

// Leeds: everything answers, one probe to London lost eight tenths of a second in.
const RUN_A = {
  id: 'a1b2c3d4e5', label: 'leeds',
  timestamp: '2026-08-30T10:00:00Z', duration_s: 60,
  phase_marks_s: { download: 10, upload: 20, 'idle-again': 30 },
  speed: [{ direction: 'download', mbps: 44.3 }, { direction: 'upload', mbps: 63.4 }],
  analysis: {
    local_overhead_ms: 1.1, origin: [53.8, -1.76],
    targets: {
      router: answered({ min: 1, median: 2, p95: 3, p99: 3.5, idleP95: 2, busyP95: 4,
        ms: [1, 2, 3, 3.5] }),
      london: answered({ min: 10, median: 25, p95: 38.5, p99: 40, idleP95: 19.5, busyP95: 39.5,
        ms: [10, 20, 30, 40], lost: [[5, 0.8]] }),
      'us-east': silent()
    }
  }
}

// Santander: the router here ignores probes, which is not the same as losing them.
const RUN_B = {
  id: 'f6g7h8i9j0', label: 'santander',
  timestamp: '2026-08-31T10:00:00Z', duration_s: 60,
  phase_marks_s: { download: 12, upload: 24, 'idle-again': 36 },
  speed: [{ direction: 'download', mbps: 175.1 }, { direction: 'upload', mbps: 224.2 }],
  analysis: {
    local_overhead_ms: 0.9, origin: [43.46, -3.8],
    targets: {
      router: silent(),
      london: answered({ min: 12, median: 30, p95: 45, p99: 50, idleP95: 28, busyP95: 32,
        ms: [12, 25, 35, 50] }),
      'us-east': silent()
    }
  }
}

/** Every colour-looking string anywhere inside a value, however deeply nested. */
function colourStrings(node, found = []) {
  if (node === null || node === undefined) return found
  if (typeof node === 'string') {
    if (/^#[0-9a-f]{3,8}$/i.test(node) || /^rgba?\(/i.test(node)) found.push(node)
    return found
  }
  if (typeof node === 'object') {
    for (const value of Object.values(node)) colourStrings(value, found)
  }
  return found
}

/** One spelling for a colour, so a wash written as rgba can be compared with its token. */
function toHex(value) {
  const parts = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(value)
  if (!parts) return value.toLowerCase()
  const [r, g, b] = parts.slice(1, 4).map(Number)
  if (r === 0 && g === 0 && b === 0 && parts[4] === '0') return 'transparent'
  return `#${[r, g, b].map(n => n.toString(16).padStart(2, '0')).join('')}`
}

const ALLOWED_COLOURS = new Set(colourStrings(TOKENS).map(toHex).concat(['transparent']))

/** Every `meta.role` the figure's traces carry, one entry per trace, missing ones included. */
function roles(figure) {
  return figure.data.map(trace => (trace.meta || {}).role)
}

const EVERY_FIGURE = [
  ['overview', () => overviewFigure([RUN_A, RUN_B], TOKENS)],
  ['penalty', () => penaltyFigure([RUN_A, RUN_B], TOKENS)],
  ['histogram', () => histogramFigure([RUN_A, RUN_B], 'london', TOKENS)],
  ['timeline', () => timelineFigure(RUN_A, 0, 'london', [0, 60], TOKENS)]
]

for (const [name, build] of EVERY_FIGURE) {
  test(`${name}: every trace carries a role the theme swap knows`, () => {
    const figure = build()
    assert.ok(figure.data.length > 0, 'the figure drew nothing to check')
    for (const role of roles(figure)) {
      assert.ok(ROLES.includes(role), `a trace carries the role ${JSON.stringify(role)}`)
    }
  })

  test(`${name}: every colour comes from the tokens`, () => {
    const figure = build()
    // Both the traces and the layout: a threshold line or a phase band written in a
    // literal hex would stop following the theme just as quietly as a trace would.
    for (const colour of colourStrings(figure)) {
      assert.ok(ALLOWED_COLOURS.has(toHex(colour)), `${colour} is not in the tokens`)
    }
  })
}

test('the overview draws a bar and a p95 mark per run, and drops a silent target', () => {
  const figure = overviewFigure([RUN_A, RUN_B], TOKENS)
  const bars = figure.data.filter(trace => trace.type === 'bar')
  const marks = figure.data.filter(trace => trace.type === 'scatter')
  assert.equal(bars.length, 2)
  assert.equal(marks.length, 2)
  assert.equal(bars[0].marker.color, TOKENS.runSlots.light[0])
  assert.equal(bars[1].marker.color, TOKENS.runSlots.light[1])
  // us-east answered in neither run, so it has no band at all; router answered in one, so
  // it keeps its band and the run that heard nothing simply has no bar in it.
  assert.deepEqual(figure.layout.yaxis.ticktext, ['router', 'london'])
  assert.deepEqual(bars[0].x, [2, 25])
  assert.deepEqual(bars[1].x, [null, 30])
  assert.deepEqual(marks[1].x, [null, 45])
})

test('the overview stacks the targets top to bottom in the tokens order', () => {
  const figure = overviewFigure([RUN_A], TOKENS)
  assert.deepEqual(figure.layout.yaxis.tickvals, [0, 1])
  // Reversed, so tick 0 (router, first in the tokens order) is at the top of the chart.
  assert.deepEqual(figure.layout.yaxis.range, [1.5, -0.5])
})

test('a run keeps its own bar and its own mark inside a target band', () => {
  const figure = overviewFigure([RUN_A, RUN_B], TOKENS)
  const [barA, markA, barB, markB] = figure.data
  // The p95 mark has to sit at the same height as the bar it belongs to, or three runs'
  // marks all land in the middle of the band and the chart says something untrue.
  assert.deepEqual(markA.y, barA.y)
  assert.deepEqual(markB.y, barB.y)
  assert.notDeepEqual(barA.y, barB.y)
  // A band is one unit of the axis, so the bar thickness in units times the band's height
  // in pixels is the bar's thickness in pixels: the dataviz cap is 14.
  const bandPx = (figure.layout.height - 60) / 2
  assert.ok(barA.width * bandPx <= 14 + 1e-9, 'the bars are thicker than 14 px')
})

test('the penalty chart draws both thresholds where the tokens put them', () => {
  const figure = penaltyFigure([RUN_A, RUN_B], TOKENS)
  const lines = figure.layout.shapes.filter(shape => shape.type === 'line')
  assert.deepEqual(lines.map(line => line.x0), [50.0, 200.0])
  assert.deepEqual(lines.map(line => line.x1), [50.0, 200.0])
  assert.deepEqual(figure.layout.annotations.map(note => note.text), ['warning', 'critical'])
  // Busy p95 minus idle p95: London went from 19.5 to 39.5 in Leeds, 28 to 32 in Santander.
  const bars = figure.data.filter(trace => trace.type === 'bar')
  assert.deepEqual(bars[0].x, [2, 20])
  assert.deepEqual(bars[1].x, [null, 4])
})

test('the histogram puts both runs on the same bins', () => {
  const figure = histogramFigure([RUN_A, RUN_B], 'london', TOKENS)
  assert.equal(figure.data.length, 2)
  assert.deepEqual(figure.data[0].x, figure.data[1].x)
  // The bins span the smallest best round trip to the largest p99 with headroom: 10 to
  // 50 * 1.05, in 30 steps, so the outlines are measuring the same thing.
  assert.equal(figure.data[0].x[0], 10)
  assert.equal(figure.data[0].x[figure.data[0].x.length - 1], 52.5)
  assert.equal(figure.data[0].line.shape, 'hv')
  assert.equal(figure.data[0].line.width, 2)
  // Each run's own name written on its peak, so identity never rests on colour alone.
  assert.ok(figure.data[0].text.includes('leeds'))
  assert.ok(figure.data[1].text.includes('santander'))
})

test('the histogram of a target nobody measured is empty rather than broken', () => {
  const figure = histogramFigure([RUN_A, RUN_B], 'madrid', TOKENS)
  assert.deepEqual(figure.data, [])
  assert.ok(figure.layout.height > 0)
})

test('a timeline keeps the scale it is handed', () => {
  const figure = timelineFigure(RUN_A, 1, 'london', [180, 280], TOKENS)
  assert.deepEqual(figure.layout.yaxis.range, [180, 280])
  const points = figure.data[0]
  assert.equal(points.marker.color, TOKENS.runSlots.light[1])
  assert.deepEqual(points.x, [0, 0.2, 0.4, 0.6000000000000001])
  assert.deepEqual(points.y, [10, 20, 30, 40])
})

test('lost probes sit on the floor of the shared scale, not at zero', () => {
  const figure = timelineFigure(RUN_A, 0, 'london', [180, 280], TOKENS)
  const lost = figure.data.find(trace => (trace.meta || {}).role === 'lost')
  assert.deepEqual(lost.x, [0.8])
  // Zero here would drop the cross clean off the bottom of a panel scaled 180 to 280.
  assert.deepEqual(lost.y, [180])
  assert.equal(lost.marker.color, TOKENS.status.critical)
})

test('a timeline shades the download and upload phases from the marks of its own run', () => {
  const figure = timelineFigure(RUN_B, 2, 'london', [0, 60], TOKENS)
  const bands = figure.layout.shapes.filter(shape => shape.type === 'rect')
  assert.deepEqual(bands.map(band => [band.x0, band.x1]), [[12, 24], [24, 36]])
  assert.deepEqual(figure.layout.annotations.map(note => note.text), ['download', 'upload'])
  // Runs start their speed test at different seconds, which is why these panels sit side
  // by side: Leeds downloads from 10 s, Santander from 12 s.
  const other = timelineFigure(RUN_A, 0, 'london', [0, 60], TOKENS)
  assert.equal(other.layout.shapes[0].x0, 10)
})

test('a timeline of a silent target draws no points and still lays out', () => {
  const figure = timelineFigure(RUN_B, 1, 'router', [0, 60], TOKENS)
  assert.deepEqual(figure.data[0].x, [])
  assert.equal(figure.data.length, 1)
})

test('a run label is escaped before plotly renders it', () => {
  const cheeky = { ...RUN_A, label: '<b>&quot;' }
  const figure = overviewFigure([cheeky], TOKENS)
  assert.equal(figure.data[0].name, '&lt;b&gt;&amp;quot;')
})

test('the legend appears only once there are two runs to tell apart', () => {
  assert.equal(overviewFigure([RUN_A], TOKENS).layout.showlegend, false)
  assert.equal(overviewFigure([RUN_A, RUN_B], TOKENS).layout.showlegend, true)
  // One panel, one run: naming it in a legend would say nothing the heading does not.
  assert.equal(timelineFigure(RUN_A, 0, 'london', [0, 60], TOKENS).layout.showlegend, false)
})

test('a run keeps the slot it was given, not the place it sits in the list', () => {
  // Untick the first of three runs and the survivors keep their colours: the second run
  // still carries slot 1, even though it is now first in the list.
  const figure = overviewFigure([{ ...RUN_B, slot: 1 }], TOKENS)
  assert.equal(figure.data[0].marker.color, TOKENS.runSlots.light[1])
  assert.equal(figure.data[0].meta.role, 'run1')
})

test('two runs sharing a label are still separate legend entries', () => {
  // The reason this page exists is comparing the same place on different days, so the same
  // --label twice is ordinary. Grouping by the label would tie the two runs together and
  // clicking either legend entry would hide both.
  const twice = overviewFigure([RUN_A, { ...RUN_B, label: 'leeds', slot: 1 }], TOKENS)
  const [barA, markA, barB, markB] = twice.data
  assert.notEqual(barA.legendgroup, barB.legendgroup)
  // A run's p95 mark still belongs to that run's bar, which is what the grouping is for.
  assert.equal(markA.legendgroup, barA.legendgroup)
  assert.equal(markB.legendgroup, barB.legendgroup)
  const hist = histogramFigure([RUN_A, { ...RUN_B, label: 'leeds', slot: 1 }], 'london', TOKENS)
  assert.notEqual(hist.data[0].legendgroup, hist.data[1].legendgroup)
})

test('themeRoles hands back the dark steps when the page is dark', () => {
  const dark = themeRoles(TOKENS, true)
  assert.deepEqual(dark, {
    lost: '#d03b3b', muted: '#898781', run0: '#3987e5', run1: '#d95926', run2: '#199e70'
  })
  const light = themeRoles(TOKENS, false)
  assert.equal(light.run0, '#2a78d6')
  // Loss is a status colour, not one of the three run hues, so it does not change with the
  // theme: the same red means the same thing on a light page and a dark one.
  assert.equal(light.lost, dark.lost)
})
