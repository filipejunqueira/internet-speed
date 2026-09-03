// Tests for the explorer's tick state. Run them with: node --test tests/js/
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_TARGET,
  emptyState,
  isSelected,
  readState,
  selectedIds,
  slotOf,
  sortRows,
  toggleRun,
  writeState
} from '../../src/pingme/site/state.js'

const MAX_RUNS = 3

function tickAll(state, ids) {
  let current = state
  for (const id of ids) current = toggleRun(current, id, MAX_RUNS).state
  return current
}

test('a fresh state has nothing ticked and shows the newest run first', () => {
  const state = emptyState('london')
  assert.deepEqual(state.selected, [])
  assert.equal(state.target, 'london')
  assert.deepEqual(state.sort, {key: 'timestamp', dir: 'desc'})
  assert.equal(emptyState().target, DEFAULT_TARGET)
})

test('a colour follows the run, not its position: untick the first and the second stays put', () => {
  // Tick A, tick B, untick A, tick C. B was on slot 1 and must still be on slot 1, so its
  // colour does not change under the reader; C takes the slot A gave up.
  let state = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b'])
  assert.equal(slotOf(state, 'a'), 0)
  assert.equal(slotOf(state, 'b'), 1)

  state = toggleRun(state, 'a', MAX_RUNS).state
  assert.equal(slotOf(state, 'a'), null)
  assert.equal(slotOf(state, 'b'), 1)

  state = toggleRun(state, 'c', MAX_RUNS).state
  assert.equal(slotOf(state, 'c'), 0)
  assert.equal(slotOf(state, 'b'), 1)
  assert.deepEqual(selectedIds(state), ['c', 'b'])
})

test('unticking reports no refusal and leaves the run unselected', () => {
  const state = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b'])
  const result = toggleRun(state, 'b', MAX_RUNS)
  assert.equal(result.refused, false)
  assert.equal(isSelected(result.state, 'b'), false)
  assert.equal(isSelected(result.state, 'a'), true)
})

test('a fourth tick is refused and changes nothing', () => {
  const three = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b', 'c'])
  assert.deepEqual(selectedIds(three), ['a', 'b', 'c'])

  const result = toggleRun(three, 'd', MAX_RUNS)
  assert.equal(result.refused, true)
  assert.equal(result.state, three)
  assert.deepEqual(selectedIds(result.state), ['a', 'b', 'c'])
  assert.equal(slotOf(result.state, 'd'), null)
})

test('the cap comes from the caller, not from this file', () => {
  // The page reads maxRuns out of the tokens block, so a number other than three has to
  // work: with two slots the third tick is refused.
  const two = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b'])
  assert.deepEqual(selectedIds(two), ['a', 'b'])
  const result = toggleRun(two, 'c', 2)
  assert.equal(result.refused, true)
  assert.equal(result.state, two)
})

test('the URL round trip keeps every run on the slot it held', () => {
  // The two rules compose here: writeState emits the ids in slot order and readState hands
  // slots out by position, so with no gap in the slots the link opens in the same colours
  // as well as the same order; the test about a slot left free is where that stops holding.
  let state = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b'])
  state = toggleRun(state, 'a', MAX_RUNS).state
  state = toggleRun(state, 'c', MAX_RUNS).state

  const restored = readState(writeState(state), DEFAULT_TARGET)
  assert.equal(slotOf(restored, 'c'), 0)
  assert.equal(slotOf(restored, 'b'), 1)
  assert.deepEqual(restored.selected, state.selected)
})

test('the query string carries ticks, a non-default target and a sort', () => {
  let state = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b'])
  state = {...state, target: 'london', sort: {key: 'p95', dir: 'asc'}}
  assert.equal(writeState(state), '?runs=a,b&target=london&sort=p95:asc')
  assert.deepEqual(readState(writeState(state), DEFAULT_TARGET), state)
})

test('an empty selection on the default target writes no query string', () => {
  const state = emptyState(DEFAULT_TARGET)
  assert.equal(writeState(state), '')
  assert.deepEqual(readState('', DEFAULT_TARGET), state)
  // A non-default sort is worth carrying even with nothing ticked: the picker table is on
  // the page either way, and a state that writes something has to read back the same.
  const sorted = {...state, sort: {key: 'p95', dir: 'asc'}}
  assert.equal(writeState(sorted), '?sort=p95:asc')
  assert.deepEqual(readState(writeState(sorted), DEFAULT_TARGET), sorted)
})

test('a link written with a slot free comes back with the runs packed onto the low slots', () => {
  // Tick a, b, c then untick b, so a holds slot 0 and c holds slot 2 with a gap between
  // them. The URL carries the order and not the numbers, so the reader who opens the link
  // gets a on 0 and c on 1: the same two runs in the same order, c in a different colour.
  let state = tickAll(emptyState(DEFAULT_TARGET), ['a', 'b', 'c'])
  state = toggleRun(state, 'b', MAX_RUNS).state
  assert.equal(slotOf(state, 'c'), 2)

  const restored = readState(writeState(state), DEFAULT_TARGET)
  assert.deepEqual(selectedIds(restored), ['a', 'c'])
  assert.equal(slotOf(restored, 'a'), 0)
  assert.equal(slotOf(restored, 'c'), 1)
})

test('a non-default target alone is enough to write a query string', () => {
  const state = {...emptyState('madrid')}
  assert.equal(writeState(state), '?target=madrid')
  assert.deepEqual(readState('?target=madrid', DEFAULT_TARGET), state)
})

test('readState survives rubbish', () => {
  const fallback = emptyState(DEFAULT_TARGET)

  // An unknown target falls back rather than asking the page for a target that cannot exist.
  assert.equal(readState('?target=atlantis', DEFAULT_TARGET).target, DEFAULT_TARGET)

  // Never more than three ticks, however many ids the URL names, and never the same run twice.
  const four = readState('?runs=a,b,c,d', DEFAULT_TARGET)
  assert.deepEqual(selectedIds(four), ['a', 'b', 'c'])
  assert.deepEqual(selectedIds(readState('?runs=a,a,b', DEFAULT_TARGET)), ['a', 'b'])
  assert.deepEqual(selectedIds(readState('?runs=,,a, b ', DEFAULT_TARGET)), ['a', 'b'])

  // A sort has to name a column and a direction to be believed.
  for (const bad of ['?sort=p95', '?sort=p95:sideways', '?sort=:asc', '?sort=']) {
    assert.deepEqual(readState(bad, DEFAULT_TARGET).sort, fallback.sort, bad)
  }

  // With or without the leading question mark, and with nothing at all.
  assert.deepEqual(selectedIds(readState('runs=a', DEFAULT_TARGET)), ['a'])
  assert.deepEqual(readState(undefined, DEFAULT_TARGET), fallback)
})

test('sortRows returns a new array and leaves the original alone', () => {
  const rows = [{id: 'a', p95: 2}, {id: 'b', p95: 1}]
  const sorted = sortRows(rows, 'p95', 'asc')
  assert.notEqual(sorted, rows)
  assert.deepEqual(rows.map(r => r.id), ['a', 'b'])
  assert.deepEqual(sorted.map(r => r.id), ['b', 'a'])
})

test('missing values sink to the bottom in both directions', () => {
  // worst_burst_probes is null for a run published before bursts were counted and 0 for a
  // run that measured and lost nothing. The null one belongs at the bottom either way; the
  // zero is a real figure and sorts with the numbers.
  const rows = [
    {id: 'old', worst_burst_probes: null},
    {id: 'clean', worst_burst_probes: 0},
    {id: 'unset', worst_burst_probes: undefined},
    {id: 'bad', worst_burst_probes: 7}
  ]
  assert.deepEqual(
    sortRows(rows, 'worst_burst_probes', 'asc').map(r => r.id),
    ['clean', 'bad', 'old', 'unset']
  )
  assert.deepEqual(
    sortRows(rows, 'worst_burst_probes', 'desc').map(r => r.id),
    ['bad', 'clean', 'old', 'unset']
  )
})

test('rows that tie keep the order they came in, in both directions', () => {
  // Three rows share a value, so a comparator that reversed the whole array or shuffled
  // equals would show: the tied group has to read first, second, fourth either way.
  const rows = [
    {id: 'first', medium: 'wifi'},
    {id: 'second', medium: 'wifi'},
    {id: 'third', medium: 'ethernet'},
    {id: 'fourth', medium: 'wifi'}
  ]
  assert.deepEqual(
    sortRows(rows, 'medium', 'asc').map(r => r.id),
    ['third', 'first', 'second', 'fourth']
  )
  assert.deepEqual(
    sortRows(rows, 'medium', 'desc').map(r => r.id),
    ['first', 'second', 'fourth', 'third']
  )
})

test('strings sort by name and numbers by size', () => {
  const rows = [
    {id: 'c', isp: 'Three', download_mbps: 44.3},
    {id: 'a', isp: 'BT', download_mbps: 175.1},
    {id: 'b', isp: 'Vodafone', download_mbps: 9.5}
  ]
  assert.deepEqual(sortRows(rows, 'isp', 'asc').map(r => r.id), ['a', 'c', 'b'])
  assert.deepEqual(sortRows(rows, 'download_mbps', 'desc').map(r => r.id), ['a', 'c', 'b'])
})

test('an unknown column leaves the rows as they were', () => {
  const rows = [{id: 'a'}, {id: 'b'}, {id: 'c'}]
  assert.deepEqual(sortRows(rows, 'nonsense', 'asc').map(r => r.id), ['a', 'b', 'c'])
  assert.deepEqual(sortRows(rows, 'nonsense', 'desc').map(r => r.id), ['a', 'b', 'c'])
})
