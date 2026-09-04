// The HTML the explorer is built from: escaping, the missing-value mark, and the hooks the
// stylesheet and the click handling reach for (the data-id and data-target attributes, the
// "on" class on a ticked row, "best" on a winning cell).
//
// Run with: node --test tests/js/

import {test} from 'node:test'
import assert from 'node:assert/strict'

import {
  burstText, chartCard, detailFrame, diffTable, emptyCard, esc, fmt, hopTable, pickerTable,
  prettyTarget, refusedNote, runName, runTiles, shortName, swatch, targetSelector
} from '../../src/pingme/site/dom.js'

const DASH = '—'

// The same shape render_web.explorer_tokens() writes into the page.
const TOKENS = {
  runSlots: {light: ['#2a78d6', '#eb6834', '#1baf7a'], dark: ['#3987e5', '#d95926', '#199e70']},
  status: {good: '#0ca30c', warning: '#fab219', serious: '#ec835a', critical: '#d03b3b'},
  targetOrder: ['router', 'isp-hop', 'london', 'madrid', 'us-east', 'sao-paulo'],
  thresholds: {lossWarn: 1.0, lossCrit: 5.0, penaltyWarn: 50.0, penaltyCrit: 200.0,
               burstWarn: 2, burstCrit: 5},
  intervalS: 0.2,
  maxRuns: 3
}

function summaryRow(over = {}) {
  return Object.assign({
    id: 'leeds_bt_2026-08-30T15-32-20Z',
    label: 'leeds',
    timestamp: '2026-08-30T15:32:20Z',
    isp: 'British Telecommunications PLC',
    city: 'Leeds',
    country: 'United Kingdom',
    medium: 'wifi',
    duration_s: 60.0,
    traced: true,
    download_mbps: 44.3,
    upload_mbps: 63.4,
    worst_loss_pct: 2.5,
    worst_burst_probes: 3,
    local_overhead_ms: 3.1,
    sao_paulo_p95_ms: 236.4,
    sao_paulo_route: 'via the USA',
    page: 'runs/leeds_bt_2026-08-30T15-32-20Z.html'
  }, over)
}

// A whole run record, of the shape runs/<id>.json holds.
function runRecord(over = {}) {
  return Object.assign({
    id: 'leeds_bt_2026-08-30T15-32-20Z',
    label: 'leeds',
    timestamp: '2026-08-30T15:32:20Z',
    duration_s: 60.0,
    snapshot: {medium: 'wifi', public: {isp: 'BT', city: 'Leeds', country: 'United Kingdom'}},
    speed: [{direction: 'download', mbps: 44.3}, {direction: 'upload', mbps: 63.4}],
    analysis: {targets: {}}
  }, over)
}

function targetEntry(sent, received, lossPct, over = {}) {
  return Object.assign({
    ip: '1.2.3.4',
    silent: false,
    samples: [[1, 12.0, 0.2, 'idle']],
    all: {sent: sent, received: received, loss_pct: lossPct, p95_ms: 30.0}
  }, over)
}

test('esc neutralises the characters that would end an attribute or open a tag', () => {
  assert.equal(esc('<script>alert("x")</script>'),
    '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;')
  assert.equal(esc("Tom & Jerry's"), 'Tom &amp; Jerry&#39;s')
  assert.equal(esc(''), '')
  assert.equal(esc(null), '')
  assert.equal(esc(undefined), '')
  assert.equal(esc(42), '42')
})

test('a run label full of markup lands in the page as text, not as tags', () => {
  const row = summaryRow({label: '<img src=x onerror="boom()">'})
  const html = pickerTable([row], {selected: [], sort: {key: 'timestamp', dir: 'desc'}}, TOKENS)
  assert.ok(!html.includes('<img'), 'the label must not reach the page as a tag')
  assert.ok(html.includes('&lt;img src=x onerror=&quot;boom()&quot;&gt;'))
})

test('fmt shows an em dash for a missing number, never 0 and never "null"', () => {
  assert.equal(fmt(null), DASH)
  assert.equal(fmt(undefined), DASH)
  assert.equal(fmt(0), '0.0')
  assert.equal(fmt(0, 0), '0')
  assert.equal(fmt(44.34), '44.3')
  assert.equal(fmt(1234.56, 1), '1,234.6')
  assert.equal(fmt(236.4, 0, ' ms'), '236 ms')
  assert.equal(fmt(NaN), DASH)
})

test('never counted and counted zero read differently', () => {
  assert.equal(burstText(null), DASH)
  assert.equal(burstText(undefined), DASH)
  assert.equal(burstText(0), '0')
  assert.equal(burstText(3), '3')
})

test('a swatch takes the run colour, and is transparent when the run is not ticked', () => {
  assert.ok(swatch(1, TOKENS).includes('#eb6834'))
  assert.ok(swatch(1, TOKENS).includes('data-slot="1"'))
  assert.ok(swatch(null, TOKENS).includes('transparent'))
  assert.ok(!swatch(null, TOKENS).includes('#'))
})

test('runName and shortName fall back to the id when the run has no label', () => {
  const unlabelled = summaryRow({label: null})
  assert.equal(runName(summaryRow()), 'leeds')
  assert.equal(runName(unlabelled), 'leeds_bt_2026-08-30T15-32-20Z')
  // where space is tight, ten characters of the id stand in for the whole thing
  assert.equal(shortName(unlabelled), 'leeds_bt_2')
})

test('every picker row carries its id, and only the ticked ones carry class on', () => {
  const rows = [summaryRow(), summaryRow({id: 'santander', label: 'santander'})]
  const state = {selected: [{id: 'santander', slot: 0}], sort: {key: 'timestamp', dir: 'desc'}}
  const html = pickerTable(rows, state, TOKENS)
  assert.ok(html.startsWith('<table class="picker">'))
  assert.ok(html.includes('data-id="leeds_bt_2026-08-30T15-32-20Z"'))
  assert.ok(html.includes('data-id="santander"'))
  assert.equal((html.match(/<tr data-id=/g) || []).length, 2)
  assert.ok(html.includes('<tr data-id="santander" class="on">'))
  assert.ok(html.includes('<tr data-id="leeds_bt_2026-08-30T15-32-20Z">'))
  assert.equal((html.match(/<span class="tick on">/g) || []).length, 1)
})

test('one run ticked gets no colour chip, two or three get one each', () => {
  const rows = [summaryRow(), summaryRow({id: 'santander', label: 'santander'})]
  const sort = {key: 'timestamp', dir: 'desc'}
  // With one run ticked the report below is that run's own page, which draws London,
  // Madrid and US-East in these very three colours: a chip would read as one of those.
  // It keeps its space though, drawn transparent. Removing the element outright shifted
  // the whole name column sideways on the first tick and back again on the second.
  const one = pickerTable(rows, {selected: [{id: 'santander', slot: 0}], sort}, TOKENS)
  assert.equal((one.match(/class="sw"/g) || []).length, 2, 'the chips hold their space')
  assert.ok(!one.includes('#2a78d6'), 'but none of them carries a run colour')
  assert.equal((one.match(/background:transparent/g) || []).length, 2)
  assert.ok(one.includes('santander'), 'the name is still there')

  // Two ticked and the chips are the legend for every chart below, so they come back.
  const two = pickerTable(rows, {selected: [{id: 'santander', slot: 0},
                                            {id: summaryRow().id, slot: 1}], sort}, TOKENS)
  assert.equal((two.match(/class="sw"/g) || []).length, 2)
  assert.ok(two.includes('#2a78d6') && two.includes('#eb6834'))
  assert.ok(!two.includes('transparent'), 'both rows are ticked, so neither chip is empty')

  // Nothing ticked: every row keeps its empty chip, so the names stay in one column.
  const none = pickerTable(rows, {selected: [], sort}, TOKENS)
  assert.equal((none.match(/transparent/g) || []).length, 2)
})

test('the sorted column is marked, and only that one', () => {
  const state = {selected: [], sort: {key: 'download_mbps', dir: 'asc'}}
  const html = pickerTable([summaryRow()], state, TOKENS)
  assert.ok(html.includes('data-sort="download_mbps" class="num sorted">down / up Mbit/s' +
    '<span class="arr">▴</span>'))
  assert.equal((html.match(/class="arr"/g) || []).length, 1)
  assert.ok(html.includes('data-sort="timestamp"'), 'every column stays clickable')
  const desc = pickerTable([summaryRow()], {selected: [], sort: {key: 'timestamp', dir: 'desc'}},
    TOKENS)
  assert.ok(desc.includes('data-sort="timestamp" class="sorted">date (UTC)' +
    '<span class="arr">▾</span>'))
})

test('a picker row shows an em dash where the run has no figure', () => {
  const row = summaryRow({worst_loss_pct: null, worst_burst_probes: null, isp: null,
                          duration_s: null})
  const html = pickerTable([row], {selected: [], sort: {}}, TOKENS)
  assert.equal((html.match(new RegExp(DASH, 'g')) || []).length, 4)
  // a measured zero is still a zero
  const zero = pickerTable([summaryRow({worst_burst_probes: 0})], {selected: [], sort: {}}, TOKENS)
  assert.ok(zero.includes('<td class="num">0</td>'))
})

test('the tiles give a green badge only when nothing at all was lost', () => {
  const clean = runRecord({analysis: {targets: {london: targetEntry(300, 300, 0.0)}}})
  const state = {selected: [{id: clean.id, slot: 0}], sort: {}}
  const html = runTiles([clean], state, TOKENS)
  assert.ok(html.startsWith('<div class="runs">'))
  assert.ok(html.includes('<span class="badge good">✓ good</span>'))
  assert.ok(html.includes('0 <small>probes lost</small>'))

  const lossy = runRecord({analysis: {targets: {london: targetEntry(300, 294, 2.0)}}})
  const bad = runTiles([lossy], state, TOKENS)
  assert.ok(bad.includes('class="badge serious"'), 'two per cent loss is not green')
  assert.ok(!bad.includes('badge good'))
  assert.ok(bad.includes('6 <small>probes lost</small>'))

  const heavy = runRecord({analysis: {targets: {london: targetEntry(300, 270, 10.0)}}})
  assert.ok(runTiles([heavy], state, TOKENS).includes('class="badge critical"'))
})

test('the tiles count lost probes across the targets that answer, and skip the silent one', () => {
  const run = runRecord({analysis: {targets: {
    router: targetEntry(300, 300, 0.0),
    'isp-hop': targetEntry(300, 0, null, {silent: true, samples: []}),
    london: targetEntry(300, 295, 1.7)
  }}})
  const html = runTiles([run], {selected: [{id: run.id, slot: 1}], sort: {}}, TOKENS)
  assert.ok(html.includes('5 <small>probes lost</small>'), 'the silent hop adds nothing')
  assert.ok(html.includes('#eb6834'), 'the tile wears the colour of the run slot')
  assert.ok(html.includes('2026-08-30 15:32'))
  assert.ok(html.includes('44.3 / 63.4'))
})

test('a run saved before the silent flag still leaves its silent hop out of the count', () => {
  // Old records carry neither "silent" nor "loss": no samples and no error means no replies.
  const old = runRecord({analysis: {targets: {
    'isp-hop': {ip: '10.0.0.1', error: null, samples: [],
                all: {sent: 300, received: 0, loss_pct: 100.0}},
    london: {ip: '1.2.3.4', error: null, samples: [[1, 12.0, 0.2, 'idle']],
             all: {sent: 300, received: 300, loss_pct: 0.0}}
  }}})
  const html = runTiles([old], {selected: [{id: old.id, slot: 0}], sort: {}}, TOKENS)
  assert.ok(html.includes('0 <small>probes lost</small>'))
  assert.ok(html.includes('badge good'), 'a hop that never answers is not a hundred per cent loss')
})

test('a run with nothing to count shows an em dash and no badge at all', () => {
  const empty = runRecord({analysis: {targets: {}}, speed: []})
  const html = runTiles([empty], {selected: [{id: empty.id, slot: 0}], sort: {}}, TOKENS)
  assert.ok(html.includes(`${DASH} <small>probes lost</small>`))
  assert.ok(!html.includes('badge'))
})

test('the comparison table marks exactly the cell the row calls best', () => {
  const rows = [
    {label: 'p95 ms', values: [236.4, 83.8], nd: 1, bestIndex: 1},
    {label: 'download Mbit/s', values: [44.3, 175.1], nd: 1, bestIndex: 1},
    {label: 'longest burst', values: [3, 3], nd: 0, bestIndex: null}
  ]
  const runs = [runRecord(), runRecord({id: 'santander', label: 'santander'})]
  const html = diffTable(rows, runs, 'sao-paulo', TOKENS)
  assert.ok(html.startsWith('<table class="diff">'))
  assert.equal((html.match(/class="num best"/g) || []).length, 2)
  assert.ok(html.includes('<td class="num best">83.8</td>'))
  assert.ok(html.includes('<td class="num">236.4</td>'))
  assert.ok(html.includes('<td class="num">3</td><td class="num">3</td>'),
    'a tie marks neither side')
  assert.ok(html.includes('<th>São Paulo</th>'), 'the header names the target')
  assert.ok(html.includes('#2a78d6') && html.includes('#eb6834'),
    'each run keeps its colour in the header')
})

test('a slot carried on the run beats its place in the array, so a colour never moves', () => {
  // Untick the run in slot 0 and the survivor keeps slot 1, even though it is now first in
  // the array. The comparison table is not given the tick state, so the record must say so.
  const rows = [{label: 'p95 ms', values: [83.8], nd: 1, bestIndex: null}]
  const survivor = runRecord({id: 'santander', label: 'santander', slot: 1})
  assert.ok(diffTable(rows, [survivor], 'sao-paulo', TOKENS).includes('#eb6834'))
  assert.ok(runTiles([survivor], {selected: [], sort: {}}, TOKENS).includes('#eb6834'))
  // with no slot anywhere, the array order is the last resort
  const bare = runRecord({id: 'santander', label: 'santander'})
  assert.ok(diffTable(rows, [bare], 'sao-paulo', TOKENS).includes('#2a78d6'))
})

test('the comparison table writes an em dash where a run has no value for a row', () => {
  const rows = [{label: 'longest burst', values: [null, 4], nd: 0, bestIndex: null}]
  const html = diffTable(rows, [runRecord(), runRecord({id: 'b'})], 'london', TOKENS)
  assert.ok(html.includes(`<td class="num">${DASH}</td>`))
  assert.ok(!html.includes('best'), 'a lone value never wins')
})

test('the target selector marks the chosen target and no other', () => {
  const html = targetSelector(['router', 'london', 'sao-paulo'], 'london')
  assert.ok(html.startsWith('<div class="filter">Drill into one target: <span class="seg">'))
  assert.ok(html.includes('<span data-target="london" class="on">London</span>'))
  assert.ok(html.includes('<span data-target="sao-paulo">São Paulo</span>'))
  assert.equal((html.match(/class="on"/g) || []).length, 1)
})

test('the detail frame points at the published page for that run, and links to it', () => {
  const html = detailFrame('leeds_bt_2026-08-30T15-32-20Z')
  assert.ok(html.includes('<iframe class="frame" data-run="leeds_bt_2026-08-30T15-32-20Z"'))
  assert.ok(html.includes('src="runs/leeds_bt_2026-08-30T15-32-20Z.html"'))
  assert.ok(html.includes('<a href="runs/leeds_bt_2026-08-30T15-32-20Z.html"'))
})

// One entry of the shape map.hopRows() returns: a run, its slot, and the drawn points
// with the origin already dropped.
function hopEntry(over = {}) {
  return Object.assign({
    id: 'leeds_bt_2026-08-30T15-32-20Z',
    label: 'leeds',
    slot: 0,
    points: [
      {n: 1, city: 'Leeds', ip: '192.168.1.1', ms: 3.2, step: null, hiddenBefore: 0},
      {n: 2, city: null, ip: '212.140.0.1', ms: 12.5, step: 9.3, hiddenBefore: 1},
      {n: 3, city: 'London', ip: '1.2.3.4', ms: 11.1, step: -1.4, hiddenBefore: 2},
      {n: 4, city: 'São Paulo', ip: null, ms: null, step: null, hiddenBefore: 0}
    ]
  }, over)
}

test('nothing traced, nothing written: the hop table is empty rather than a bare summary', () => {
  assert.equal(hopTable([], TOKENS), '')
  assert.equal(hopTable(null, TOKENS), '')
  assert.equal(hopTable(undefined, TOKENS), '')
})

test('the hop table writes out every value the map only shows on hover', () => {
  const html = hopTable([hopEntry()], TOKENS)
  assert.ok(html.startsWith('<details><summary>every hop, and where the time goes</summary>'))
  assert.ok(html.endsWith('</details>'))
  assert.equal((html.match(/<table class="stats hops">/g) || []).length, 1)
  // the run is named once, in a caption row above the column heads, wearing its colour
  assert.ok(html.includes('<tr><th colspan="5"><span class="sw" data-slot="0" ' +
    'style="background:#2a78d6"></span>leeds</th></tr>'))
  assert.ok(html.includes('<th>#</th><th>address</th><th>placed</th>' +
    '<th>reached in ms</th><th>added ms</th>'))
  assert.ok(html.includes('<tr><th>1</th><td>192.168.1.1</td><td>Leeds</td>' +
    `<td>3.2</td><td>${DASH}</td></tr>`), 'the first point has nothing to add to')
  assert.ok(html.includes('<td>London</td><td>11.1</td>'))
  // an address, a place or a delay the trace never got is an em dash, not a blank or a 0
  assert.ok(html.includes(`<tr><th>4</th><td>${DASH}</td><td>São Paulo</td>` +
    `<td>${DASH}</td><td>${DASH}</td></tr>`))
})

test('a hop that answers sooner than the one before it keeps its minus sign', () => {
  const html = hopTable([hopEntry()], TOKENS)
  assert.ok(html.includes('<td>+9.3</td>'), 'the usual step is signed too')
  assert.ok(html.includes('<td>-1.4</td>'), 'a negative step is real and stays negative')
})

test('the hops that never answered are counted in a muted row of their own', () => {
  const html = hopTable([hopEntry()], TOKENS)
  assert.ok(html.includes('<tr class="quiet"><th colspan="5">1 hop did not answer</th></tr>'))
  assert.ok(html.includes('<tr class="quiet"><th colspan="5">2 hops did not answer</th></tr>'))
  assert.equal((html.match(/class="quiet"/g) || []).length, 2,
    'a point with nothing hidden before it gets no row')
})

test('one table per run, each in its own colour', () => {
  const html = hopTable([hopEntry(), hopEntry({id: 'santander', label: 'santander', slot: 1})],
    TOKENS)
  assert.equal((html.match(/<table class="stats hops">/g) || []).length, 2)
  assert.equal((html.match(/<details>/g) || []).length, 1, 'one collapsed block holds them all')
  assert.ok(html.includes('#2a78d6') && html.includes('#eb6834'))
  assert.ok(html.indexOf('leeds') < html.indexOf('santander'), 'slot order is kept')
})

test('a hop table full of markup lands in the page as text, not as tags', () => {
  const nasty = hopEntry({
    label: '<img src=x onerror="boom()">',
    points: [{n: 1, city: '<b>Leeds</b>', ip: '"><script>alert(1)</script>', ms: 3.2,
              step: null, hiddenBefore: 0}]
  })
  const html = hopTable([nasty], TOKENS)
  assert.ok(!html.includes('<img') && !html.includes('<script>'))
  assert.ok(html.includes('&lt;img src=x onerror=&quot;boom()&quot;&gt;'))
  assert.ok(html.includes('&lt;b&gt;Leeds&lt;/b&gt;'))
  assert.ok(html.includes('&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;'))
})

test('the small cards say their piece', () => {
  assert.ok(emptyCard().includes('<section class="card empty">'))
  assert.ok(refusedNote(3).startsWith('<p class="refused">3 runs at most:'))
  assert.equal(chartCard('Round trip over time', '<div id="x"></div>'),
    '<section class="card"><h2>Round trip over time</h2><div id="x"></div></section>')
})

test('a card heading takes an id when the page has to rewrite it later', () => {
  // The cards whose titles name the chosen target are edited in place when the reader picks
  // another one, rather than being built again, because rebuilding the card would throw
  // away the plotly figure standing inside it.
  assert.equal(chartCard('The route to São Paulo', '<div id="fig-map"></div>', 'head-map'),
    '<section class="card"><h2 id="head-map">The route to São Paulo</h2>' +
    '<div id="fig-map"></div></section>')
  assert.ok(!chartCard('No id here', '').includes('id='), 'and nothing changes without one')
})

test('target names are written the way a person would write them', () => {
  assert.equal(prettyTarget('sao-paulo'), 'São Paulo')
  assert.equal(prettyTarget('us-east'), 'US-East')
  assert.equal(prettyTarget('isp-hop'), 'isp hop')
  assert.equal(prettyTarget('router'), 'router')
  assert.equal(prettyTarget('nowhere'), 'nowhere', 'an unknown target keeps its own name')
})
