// Tests for the route map: which hops become points, which legs are drawn as a guess,
// and which runs the map has nothing to show for.
//
// The traces here are hand-built, one awkward case each, because the real traces in the
// log are long and every interesting case in them is buried in the middle of forty hops.

import test from 'node:test'
import assert from 'node:assert/strict'

import { hopRows, mapFigure, routePoints, untracedRuns } from '../../src/pingme/site/map.js'

const TOKENS = {
  runSlots: { light: ['#2a78d6', '#eb6834', '#1baf7a'], dark: ['#3987e5', '#d95926', '#199e70'] },
  chrome: {
    light: { surface: '#fcfcfb', page: '#f9f9f7', ink: '#0b0b0b', ink2: '#52514e',
      muted: '#898781', grid: '#e1e0d9', axis: '#c3c2b7', border: 'rgba(11,11,11,0.10)' },
    dark: { surface: '#1a1a19', page: '#0d0d0d', ink: '#ffffff', ink2: '#c3c2b7',
      muted: '#898781', grid: '#2c2c2a', axis: '#383835', border: 'rgba(255,255,255,0.10)' }
  },
  font: 'system-ui, sans-serif'
}

const LEEDS = [53.8, -1.76]

function hop(n, ip, avg_ms) {
  return { n, ip, avg_ms, loss_pct: 0 }
}

function place(ip, lat, lon, city, source = 'ip-api') {
  return { ip, lat, lon, city, source, hostname: null }
}

test('the route starts at the run origin', () => {
  const points = routePoints({ error: null, hops: [], locations: [] }, LEEDS)
  assert.equal(points.length, 1)
  assert.deepEqual(
    points[0],
    { lat: 53.8, lon: -1.76, city: 'you', ip: null, ms: null, hiddenBefore: 0 })
})

test('a trace with no placed hop draws the origin and nothing else', () => {
  const entry = {
    error: null,
    hops: [hop(1, '192.168.0.1', 1.2), hop(2, null, null), hop(3, '10.0.0.1', 9.0)],
    locations: [
      place('192.168.0.1', 53.8, -1.76, null, 'private'),
      null,
      place('10.0.0.1', null, null, null, 'unknown')
    ]
  }
  assert.deepEqual(routePoints(entry, LEEDS).map(p => p.city), ['you'])
})

test('unplaced and absent hops are skipped and counted onto the next point', () => {
  const entry = {
    error: null,
    hops: [hop(1, '192.168.0.1', 1.1), hop(2, null, null), hop(3, '10.0.0.1', 8.0),
      hop(4, '81.2.3.4', 14.6)],
    locations: [
      place('192.168.0.1', 53.8, -1.76, 'Leeds', 'private'), // your own router, at the origin
      null, // no reply at all
      place('10.0.0.1', null, null, null, 'unknown'), // answered, but nowhere to put it
      place('81.2.3.4', 51.51, -0.13, 'London')
    ]
  }
  const points = routePoints(entry, LEEDS)
  assert.equal(points.length, 2)
  assert.deepEqual(points[1], { lat: 51.51, lon: -0.13, city: 'London', ip: '81.2.3.4', ms: 14.6,
    hiddenBefore: 2 }) // the router collapsed onto the origin; the other two are hidden
})

test('two hops in the same place become one point, and that is not a hidden hop', () => {
  const entry = {
    error: null,
    hops: [hop(1, '81.2.3.4', 12.0), hop(2, '81.2.3.5', 12.4), hop(3, '155.1.1.1', 210.0)],
    locations: [
      place('81.2.3.4', 51.51, -0.13, 'London'),
      place('81.2.3.5', 51.53, -0.16, 'London'), // 0.02 and 0.03 away: the same place
      place('155.1.1.1', -23.55, -46.63, 'São Paulo')
    ]
  }
  const points = routePoints(entry, LEEDS)
  assert.deepEqual(points.map(p => p.city), ['you', 'London', 'São Paulo'])
  assert.equal(points[1].ip, '81.2.3.4') // the first of the two, not the second
  assert.equal(points[2].hiddenBefore, 0) // collapsed, not hidden
})

test('a hop that answered without a timing has no delay to show', () => {
  const entry = {
    error: null,
    hops: [hop(1, '81.2.3.4', null)],
    locations: [place('81.2.3.4', 51.51, -0.13, 'London')]
  }
  assert.equal(routePoints(entry, LEEDS)[1].ms, null)
})

const SAO_PAULO = { name: 'sao-paulo', ip: '155.133.227.35', kind: 'relay',
  city: 'Sao Paulo (Brazil)', lat: -23.55, lon: -46.63, note: 'valve relay gru' }

function run(id, entry, extra = {}) {
  return {
    id, label: null, analysis: { origin: LEEDS, targets: {} },
    targets: [SAO_PAULO],
    traces: entry === null ? undefined : { 'sao-paulo': entry },
    ...extra
  }
}

const LONDON_THEN_NOTHING = {
  error: null,
  hops: [hop(1, '81.2.3.4', 12.0), hop(2, null, null), hop(3, null, null)],
  locations: [place('81.2.3.4', 51.51, -0.13, 'London'), null, null]
}

test('the leg to the relay is dashed when the last hops never answered', () => {
  const { data } = mapFigure([run('a', LONDON_THEN_NOTHING)], 'sao-paulo', TOKENS)
  const legs = data.filter(t => t.mode === 'lines')
  // Two traces, not two legs: one holds every solid leg of this run, one every dashed leg.
  // Here that is a leg each — you → London, then London → the relay.
  assert.equal(legs.length, 2)
  assert.equal(legs[0].line.dash, 'solid')
  assert.equal(legs[1].line.dash, 'dash')
  assert.match(legs[1].hovertext[0], /2 hidden hop/)
  const end = legs[1].lat[1]
  assert.equal(end, -23.55) // the relay itself closes the route
})

test('your own router is the origin star, not a hop the route skipped', () => {
  // geo puts a private address at the origin, so hop 1 lands on the star and is dropped as
  // a zero-length hop. Nothing was skipped, so both legs stay solid — the same picture the
  // run page draws for this trace — and one trace carries the pair of them.
  const entry = {
    error: null,
    hops: [hop(1, '192.168.0.1', 1.1), hop(2, '81.2.3.4', 12.0)],
    locations: [place('192.168.0.1', 53.8, -1.76, 'local network', 'private'),
      place('81.2.3.4', 51.51, -0.13, 'London')]
  }
  const { data } = mapFigure([run('a', entry)], 'sao-paulo', TOKENS)
  const legs = data.filter(t => t.mode === 'lines')
  assert.equal(legs.length, 1) // nothing is a guess here, so no dashed trace is pushed at all
  assert.equal(legs[0].line.dash, 'solid')
  // you → London, then London → the relay, with the null between them lifting the pen so
  // the two legs never join into a line that was never measured.
  assert.deepEqual(legs[0].lat, [53.8, 51.51, null, 51.51, -23.55, null])
  // The run name alone on every leg: no hidden-hop note.
  assert.deepEqual(legs[0].hovertext, ['a', 'a', '', 'a', 'a', ''])
})

test('the relay is not drawn twice when a hop already landed on it', () => {
  const onTop = {
    error: null,
    hops: [hop(1, '155.133.227.34', 209.0)],
    locations: [place('155.133.227.34', -23.56, -46.64, 'São Paulo')]
  }
  const { data } = mapFigure([run('a', onTop)], 'sao-paulo', TOKENS)
  assert.equal(data.filter(t => t.mode === 'lines').length, 1)
})

test('each leg keeps its own hover sentence inside the trace it shares', () => {
  // One dashed leg jumps a single hidden hop and the next jumps two. They sit in one trace
  // now, so the hover text has to be an array indexed against the coordinates rather than
  // one sentence for the whole line — and the null between two legs needs an entry of its
  // own, or every leg after the first would show the sentence belonging to the one before.
  const entry = {
    error: null,
    hops: [hop(1, null, null), hop(2, '81.2.3.4', 12.0), hop(3, null, null),
      hop(4, null, null), hop(5, '62.1.1.1', 20.0), hop(6, '155.1.1.1', 210.0)],
    locations: [
      null,
      place('81.2.3.4', 51.51, -0.13, 'London'),
      null,
      null,
      place('62.1.1.1', 52.37, 4.9, 'Amsterdam'),
      place('155.1.1.1', -23.55, -46.63, 'São Paulo')
    ]
  }
  const { data } = mapFigure([run('a', entry)], 'sao-paulo', TOKENS)
  const dashed = data.find(t => t.mode === 'lines' && t.line.dash === 'dash')
  assert.deepEqual(dashed.lat, [53.8, 51.51, null, 51.51, 52.37, null])
  assert.deepEqual(dashed.hovertext, ['a: 1 hidden hop(s)', 'a: 1 hidden hop(s)', '',
    'a: 2 hidden hop(s)', 'a: 2 hidden hop(s)', ''])
  assert.equal(dashed.connectgaps, false)
  const solid = data.find(t => t.mode === 'lines' && t.line.dash === 'solid')
  assert.deepEqual(solid.lat, [52.37, -23.55, null]) // Amsterdam → the relay, nothing hidden
})

test('a run whose every leg is a guess still gets one legend entry, and a dashed one', () => {
  // Nothing between the origin and the relay could be placed, so this run has no solid leg
  // and no empty solid trace is pushed for it. The legend swatch belongs to whichever trace
  // holds the first leg, which keeps it dashed here exactly as it was when every leg had a
  // trace to itself.
  const nothingPlaced = {
    error: null,
    hops: [hop(1, null, null), hop(2, null, null)],
    locations: [null, null]
  }
  const { data } = mapFigure([run('a', nothingPlaced), run('b', LONDON_THEN_NOTHING)],
    'sao-paulo', TOKENS)
  const mine = data.filter(t => t.mode === 'lines' && t.name === 'a')
  assert.equal(mine.length, 1)
  assert.equal(mine[0].line.dash, 'dash')
  assert.deepEqual(data.filter(t => t.showlegend).map(t => [t.name, t.line.dash]),
    [['a', 'dash'], ['b', 'solid']])
})

// A route of `hops` traceroute hops with every third one unplaceable, spread down a
// meridian so no two land close enough to collapse into one point. Both the solid trace
// and the dashed one end up with several legs to hold.
function longRoute(hops) {
  const walked = [], locations = []
  for (let n = 1; n <= hops; n++) {
    const hidden = n % 3 === 0
    const ip = `81.2.${n}.1`
    walked.push(hop(n, hidden ? null : ip, hidden ? null : n))
    locations.push(hidden ? null : place(ip, 51 - n * 0.5, -0.13, `hop ${n}`))
  }
  return { error: null, hops: walked, locations }
}

test('the map costs a bounded number of traces however long the routes are', () => {
  // The map used to emit one scattergeo trace per leg: 15 traces for the two runs labelled
  // leeds_bt in the log drawn against Sao Paulo, and scattergeo is the most expensive type plotly
  // has, rebuilt from scratch every time the target changes. Two line traces per run is the
  // ceiling now — one for the solid legs, one for the dashed — so the count stops following
  // the length of the route. Six hops and forty hops have to cost the same.
  for (const hops of [6, 40]) {
    const runs = [run('a', longRoute(hops)), run('b', longRoute(hops))]
    const { data } = mapFigure(runs, 'sao-paulo', TOKENS)
    const legs = data.filter(t => t.mode === 'lines')
    assert.ok(legs.length <= 4, `${hops} hops: ${legs.length} line traces, ceiling is 4`)
    // Four lines, two sets of points, the cable landings and the shared origin star.
    assert.ok(data.length <= 8, `${hops} hops: ${data.length} traces, ceiling is 8`)
  }
})

test('colour follows the run slot, not the position in the list', () => {
  // Three runs were ticked and the middle one unticked: the survivor keeps slot 2.
  const runs = [run('a', LONDON_THEN_NOTHING, { slot: 0 }),
    run('c', LONDON_THEN_NOTHING, { slot: 2 })]
  const { data } = mapFigure(runs, 'sao-paulo', TOKENS)
  const colours = data.filter(t => t.mode === 'lines').map(t => t.line.color)
  assert.deepEqual(new Set(colours), new Set([TOKENS.runSlots.light[0], TOKENS.runSlots.light[2]]))
  const roles = new Set(data.filter(t => t.mode === 'lines').map(t => t.meta.role))
  assert.deepEqual(roles, new Set(['run0', 'run2']))
})

test('with no slots attached the runs take the colours in order', () => {
  const runs = [run('a', LONDON_THEN_NOTHING), run('b', LONDON_THEN_NOTHING)]
  const { data } = mapFigure(runs, 'sao-paulo', TOKENS)
  const first = data.find(t => t.name === 'a' && t.mode === 'lines')
  const second = data.find(t => t.name === 'b' && t.mode === 'lines')
  assert.equal(first.line.color, TOKENS.runSlots.light[0])
  assert.equal(second.line.color, TOKENS.runSlots.light[1])
})

test('every run is named on its own line and hovering names the place', () => {
  const { data } = mapFigure([run('leeds', LONDON_THEN_NOTHING)], 'sao-paulo', TOKENS)
  const markers = data.find(t => t.mode === 'markers+text' && t.name === 'leeds')
  assert.deepEqual(markers.text, ['', '', 'leeds']) // only at the far end
  assert.match(markers.hovertext[1], /London/)
  assert.match(markers.hovertext[1], /81\.2\.3\.4/)
  assert.match(markers.hovertext[1], /12 ms in/)
})

test('a label is used as the run name when the run has one', () => {
  const withLabel = run('2026-09-03T13-14', LONDON_THEN_NOTHING, { label: 'santander' })
  const { data } = mapFigure([withLabel], 'sao-paulo', TOKENS)
  assert.ok(data.some(t => t.name === 'santander'))
})

test('a name or a city with markup in it cannot break the hover', () => {
  const entry = {
    error: null,
    hops: [hop(1, '81.2.3.4', 12.0)],
    locations: [place('81.2.3.4', 51.51, -0.13, '<b>Leeds</b>')]
  }
  const nasty = run('a', entry, { label: 'kitchen & <hall>' })
  const { data } = mapFigure([nasty], 'sao-paulo', TOKENS)
  const markers = data.find(t => t.mode === 'markers+text')
  assert.equal(markers.hovertext[1], '&lt;b&gt;Leeds&lt;/b&gt; (81.2.3.4, 12 ms in)<br>' +
    'kitchen &amp; &lt;hall&gt;')
  assert.ok(markers.text.every(t => !t.includes('<hall>')))
})

test('runs measured in different places each get their own star', () => {
  const here = run('leeds', LONDON_THEN_NOTHING)
  const away = run('santander', LONDON_THEN_NOTHING)
  away.analysis = { origin: [43.46, -3.8], targets: {} }
  const sameHouse = run('leeds-again', LONDON_THEN_NOTHING)
  const { data } = mapFigure([here, away, sameHouse], 'sao-paulo', TOKENS)
  const star = data.find(t => t.name === 'origin')
  assert.deepEqual(star.lat, [53.8, 43.46]) // two places, three runs
})

test('the cable landings and the origin star are always drawn', () => {
  const { data } = mapFigure([run('a', LONDON_THEN_NOTHING)], 'sao-paulo', TOKENS)
  const cables = data.find(t => t.name === 'cable landing points')
  assert.deepEqual(cables.lat, [37.95, -3.73, 40.71, 25.77])
  assert.deepEqual(cables.lon, [-8.87, -38.52, -74.0, -80.19])
  const star = data.find(t => t.name === 'origin')
  assert.deepEqual(star.lat, [53.8])
  assert.equal(star.marker.symbol, 'star')
})

test('no trace carries a hex the theme swap cannot reach', () => {
  const { data, layout } = mapFigure([run('a', LONDON_THEN_NOTHING)], 'sao-paulo', TOKENS)
  const allowed = new Set([...TOKENS.runSlots.light, TOKENS.chrome.light.muted,
    TOKENS.chrome.light.ink2])
  for (const trace of data) {
    assert.ok(trace.meta && trace.meta.role, `${trace.name} has no role for the theme swap`)
    for (const colour of [trace.line && trace.line.color, trace.marker && trace.marker.color]) {
      if (colour) assert.ok(allowed.has(colour), `unexpected colour ${colour}`)
    }
  }
  assert.equal(layout.geo.fitbounds, 'locations')
  assert.equal(layout.geo.projection.type, 'natural earth')
})

test('the legend appears only when there is more than one run to tell apart', () => {
  const one = mapFigure([run('a', LONDON_THEN_NOTHING)], 'sao-paulo', TOKENS)
  assert.equal(one.layout.showlegend, false)
  assert.equal(one.data.filter(t => t.showlegend).length, 0)
  const two = mapFigure([run('a', LONDON_THEN_NOTHING), run('b', LONDON_THEN_NOTHING)],
    'sao-paulo', TOKENS)
  assert.equal(two.layout.showlegend, true)
  assert.deepEqual(two.data.filter(t => t.showlegend).map(t => t.name), ['a', 'b'])
})

test('two runs with the same label still hide one at a time', () => {
  // The log already holds two runs both labelled leeds_bt, and comparing two runs from one
  // house is what this page is for. Grouping the legend by the name would put both routes
  // in one group, so clicking either would hide both.
  const first = run('a', LONDON_THEN_NOTHING, { label: 'leeds_bt' })
  const second = run('b', LONDON_THEN_NOTHING, { label: 'leeds_bt' })
  const { data } = mapFigure([first, second], 'sao-paulo', TOKENS)
  const groups = new Set(data.filter(t => t.mode === 'lines').map(t => t.legendgroup))
  assert.equal(groups.size, 2)
  // Every trace of one run shares a group, legs and markers alike: that is what makes one
  // click hide one whole route.
  const traces = data.filter(t => t.meta && t.meta.role === 'run0')
  assert.equal(new Set(traces.map(t => t.legendgroup)).size, 1)
  assert.ok(traces.some(t => t.mode === 'markers+text'))
  assert.deepEqual(data.filter(t => t.showlegend).map(t => t.name), ['leeds_bt', 'leeds_bt'])
})

// Three hops that never got placed, then London, then the relay itself answering.
const HIDDEN_THEN_LONDON = {
  error: null,
  hops: [hop(1, null, null), hop(2, '10.0.0.1', 5.0), hop(3, '10.0.0.2', 6.0),
    hop(4, '81.2.3.4', 12.5), hop(5, '155.1.1.1', 210.5)],
  locations: [
    null, // no reply at all
    place('10.0.0.1', null, null, null, 'unknown'), // answered, nowhere to put it
    null,
    place('81.2.3.4', 51.51, -0.13, 'London'),
    place('155.1.1.1', -23.55, -46.63, 'São Paulo')
  ]
}

test('the hop rows number the drawn points from one, not by traceroute hop', () => {
  const [entry] = hopRows([run('leeds', HIDDEN_THEN_LONDON, { label: 'leeds_bt' })], 'sao-paulo')
  assert.equal(entry.id, 'leeds')
  assert.equal(entry.label, 'leeds_bt')
  assert.equal(entry.slot, 0)
  // London is traceroute's hop 4 and the first thing drawn, so it is row 1 with the three
  // hops before it counted onto it. The origin is the map's star, not a row.
  assert.deepEqual(entry.points, [
    { n: 1, city: 'London', ip: '81.2.3.4', ms: 12.5, step: null, hiddenBefore: 3 },
    { n: 2, city: 'São Paulo', ip: '155.1.1.1', ms: 210.5, step: 198, hiddenBefore: 0 }
  ])
})

test('the added delay is null at either end of an unknown, and negative when it dips', () => {
  const entry = {
    error: null,
    hops: [hop(1, '81.2.3.4', 12.5), hop(2, '62.1.1.1', 12.0), hop(3, '155.1.1.1', null)],
    locations: [
      place('81.2.3.4', 51.51, -0.13, 'London'),
      place('62.1.1.1', 52.37, 4.9, 'Amsterdam'),
      place('155.1.1.1', -23.55, -46.63, 'São Paulo')
    ]
  }
  const [row] = hopRows([run('a', entry)], 'sao-paulo')
  assert.equal(row.points[0].step, null) // measured from the origin, which has no timing
  // Traceroute times each hop once, so a hop further along can come back sooner. That is
  // what the line did, and the table says so rather than tidying it to zero.
  assert.equal(row.points[1].step, -0.5)
  assert.equal(row.points[2].ms, null)
  assert.equal(row.points[2].step, null) // this end unknown, so nothing to subtract
})

test('a run with no route to this target has no hop rows either', () => {
  const rows = hopRows([run('old', null), run('new', HIDDEN_THEN_LONDON)], 'sao-paulo')
  assert.deepEqual(rows.map(r => r.id), ['new'])
})

test('the hop rows take the same slots the map gives the same runs', () => {
  // The middle run has no route here, so it is missing from both. If the rows counted the
  // ticked runs and the map the drawn ones, the swatch on a row would name another line.
  const runs = [run('a', HIDDEN_THEN_LONDON), run('b', null), run('c', HIDDEN_THEN_LONDON)]
  const rows = hopRows(runs, 'sao-paulo')
  assert.deepEqual(rows.map(r => r.slot), [0, 1])
  const { data } = mapFigure(runs, 'sao-paulo', TOKENS)
  const roles = [...new Set(data.filter(t => t.mode === 'lines').map(t => t.meta.role))]
  assert.deepEqual(rows.map(r => `run${r.slot}`), roles)
})

test('a slot the page attached is kept by the hop rows', () => {
  const runs = [run('a', HIDDEN_THEN_LONDON, { slot: 0 }),
    run('c', HIDDEN_THEN_LONDON, { slot: 2 })]
  assert.deepEqual(hopRows(runs, 'sao-paulo').map(r => r.slot), [0, 2])
})

test('a run with no route to this target is named rather than drawn', () => {
  const noTraces = run('old', null) // published before traces were saved with the run
  const otherTarget = run('router-only', LONDON_THEN_NOTHING)
  otherTarget.traces = { london: LONDON_THEN_NOTHING } // traced, but not to this relay
  const traced = run('new', LONDON_THEN_NOTHING)
  assert.deepEqual(untracedRuns([noTraces, otherTarget, traced], 'sao-paulo').map(r => r.id),
    ['old', 'router-only'])
  const { data } = mapFigure([noTraces, otherTarget, traced], 'sao-paulo', TOKENS)
  assert.deepEqual([...new Set(data.filter(t => t.mode === 'lines').map(t => t.name))], ['new'])
})

test('the relay ends the hop table too, so its address is not hover-only', () => {
  // The map draws the relay as the last point even when the hops before it went unanswered.
  // Without a row of its own here, the one address a reader most wants would be reachable
  // only with a pointer, which is the reason this table exists.
  const run = {
    id: 'r', label: 'r', slot: 0,
    analysis: {origin: [53.8, -1.55]},
    targets: [{name: 'sao-paulo', ip: '155.133.227.35', city: 'Sao Paulo',
      lat: -23.55, lon: -46.63}],
    traces: {'sao-paulo': {
      hops: [{n: 1, ip: '10.0.0.1', avg_ms: 3.0, loss_pct: 0},
             {n: 2, ip: null, avg_ms: null, loss_pct: null},
             {n: 3, ip: '1.2.3.4', avg_ms: 200.0, loss_pct: 0}],
      locations: [{ip: '10.0.0.1', lat: 51.5, lon: -0.13, city: 'London', source: 'ip-api'},
                  null,
                  {ip: '1.2.3.4', lat: 25.77, lon: -80.19, city: 'Miami', source: 'ip-api'}]
    }}
  }
  const [entry] = hopRows([run], 'sao-paulo')
  const last = entry.points[entry.points.length - 1]
  assert.equal(last.city, 'Sao Paulo')
  assert.equal(last.ip, '155.133.227.35')
  assert.equal(last.n, entry.points.length, 'it is numbered after the hops, not among them')
  assert.equal(last.hiddenBefore, 0, 'nothing went unanswered between Miami and the relay')

  // A relay that a hop already landed on is not written twice.
  run.targets[0].lat = 25.77
  run.targets[0].lon = -80.19
  const [same] = hopRows([run], 'sao-paulo')
  assert.equal(same.points.length, 2, 'Miami is the relay, so there is no extra row')
})
