import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  binCounts, burstProbes, diffRows, isSilent, liveTargets, lostCount, penalty,
  sharedBins, sharedYRange
} from '../../src/pingme/site/stats.js'

// Every fixture below is small enough to check on paper: four round trips per target, and
// summary figures written out rather than derived, so each expected number in the tests is
// a literal somebody can follow. Nothing here reads a real run file.

const TARGET_ORDER = ['router', 'isp-hop', 'london', 'madrid', 'us-east', 'sao-paulo']

/** An address that answered: four probes of 10, 20, 30, 40 ms, with the fifth one lost. */
const londonA = {
  ip: '203.0.113.10',
  kind: 'relay',
  error: null,
  silent: false,
  all: {
    sent: 5, received: 4, loss_pct: 20, min_ms: 10, median_ms: 25, mean_ms: 25,
    p95_ms: 38.5, p99_ms: 40, max_ms: 40, stdev_ms: 11.2, jitter_ms: 10
  },
  idle: { sent: 2, received: 2, loss_pct: 0, p95_ms: 19.5, jitter_ms: 10 },
  busy: { sent: 3, received: 2, loss_pct: 33.33, p95_ms: 39.5, jitter_ms: 10 },
  loss: { lost: [[5, 0.8]], longest_burst_probes: 1, longest_burst_s: 0.2, longest_burst_at_s: 0.8 },
  samples: [[1, 10, 0.0, 'idle'], [2, 20, 0.2, 'idle'], [3, 30, 0.4, 'download'],
    [4, 40, 0.6, 'upload']]
}

/** An address set to ignore probes: it answered nothing, and none of that is loss. */
const saoPauloSilent = {
  ip: '203.0.113.99',
  kind: 'relay',
  error: null,
  silent: true,
  all: {
    sent: 60, received: 0, loss_pct: null, min_ms: null, median_ms: null, mean_ms: null,
    p95_ms: null, p99_ms: null, max_ms: null, stdev_ms: null, jitter_ms: null
  },
  idle: { sent: 30, received: 0, loss_pct: null, p95_ms: null },
  busy: { sent: 30, received: 0, loss_pct: null, p95_ms: null },
  loss: null,
  samples: []
}

const runA = {
  id: 'aaaa1111bb',
  label: 'Leeds',
  timestamp: '2026-08-30T18:00:00+00:00',
  duration_s: 60,
  speed: [
    { direction: 'download', mbps: 44.3 },
    { direction: 'upload', mbps: 63.4 }
  ],
  analysis: {
    local_overhead_ms: 1.2,
    targets: { london: londonA, 'sao-paulo': saoPauloSilent }
  }
}

/** The same address on a slower line: four probes of 50, 60, 70, 80 ms, none lost. */
const londonB = {
  ip: '203.0.113.10',
  kind: 'relay',
  error: null,
  silent: false,
  all: {
    sent: 4, received: 4, loss_pct: 0, min_ms: 50, median_ms: 65, mean_ms: 65,
    p95_ms: 78.5, p99_ms: 80, max_ms: 80, stdev_ms: 11.2, jitter_ms: 10
  },
  idle: { sent: 2, received: 2, loss_pct: 0, p95_ms: 59.5, jitter_ms: 10 },
  busy: { sent: 2, received: 2, loss_pct: 0, p95_ms: 69.5, jitter_ms: 10 },
  loss: { lost: [], longest_burst_probes: 0, longest_burst_s: 0, longest_burst_at_s: 0 },
  samples: [[1, 50, 0.0, 'idle'], [2, 60, 0.2, 'idle'], [3, 70, 0.4, 'download'],
    [4, 80, 0.6, 'upload']]
}

const routerB = {
  ip: '192.168.1.1',
  kind: 'router',
  error: null,
  silent: false,
  all: {
    sent: 4, received: 4, loss_pct: 0, min_ms: 1, median_ms: 1, mean_ms: 1,
    p95_ms: 1, p99_ms: 1, max_ms: 1, stdev_ms: 0, jitter_ms: 0
  },
  idle: { sent: 2, received: 2, loss_pct: 0, p95_ms: 1 },
  busy: { sent: 2, received: 2, loss_pct: 0, p95_ms: 1 },
  loss: { lost: [], longest_burst_probes: 0, longest_burst_s: 0, longest_burst_at_s: 0 },
  samples: [[1, 1, 0.0, 'idle'], [2, 1, 0.2, 'idle'], [3, 1, 0.4, 'download'],
    [4, 1, 0.6, 'upload']]
}

const runB = {
  id: 'bbbb2222cc',
  label: 'Santander',
  timestamp: '2026-08-31T09:00:00+00:00',
  duration_s: 30,
  speed: [
    { direction: 'download', mbps: 175.1 },
    { direction: 'upload', mbps: 224.2 }
  ],
  analysis: {
    local_overhead_ms: 0.8,
    targets: { router: routerB, london: londonB }
  }
}

/** A third line, sitting between the other two: four probes of 30, 32, 36, 42 ms. */
const londonC = {
  ip: '203.0.113.10',
  kind: 'relay',
  error: null,
  silent: false,
  all: {
    sent: 4, received: 4, loss_pct: 0, min_ms: 30, median_ms: 35, mean_ms: 35,
    p95_ms: 41, p99_ms: 42, max_ms: 42, stdev_ms: 5, jitter_ms: 4
  },
  idle: { sent: 2, received: 2, loss_pct: 0, p95_ms: 33, jitter_ms: 4 },
  busy: { sent: 2, received: 2, loss_pct: 0, p95_ms: 38, jitter_ms: 4 },
  loss: { lost: [], longest_burst_probes: 0, longest_burst_s: 0, longest_burst_at_s: 0 },
  samples: [[1, 30, 0.0, 'idle'], [2, 32, 0.2, 'idle'], [3, 36, 0.4, 'download'],
    [4, 42, 0.6, 'upload']]
}

const runC = {
  id: 'cccc3333dd',
  label: 'Bristol',
  timestamp: '2026-09-01T12:00:00+00:00',
  duration_s: 60,
  speed: [
    { direction: 'download', mbps: 200 },
    { direction: 'upload', mbps: 100 }
  ],
  analysis: {
    local_overhead_ms: 1,
    targets: { london: londonC }
  }
}

/** A record saved before the silent flag and the burst count existed: neither key is there. */
const oldMeasured = {
  ip: '203.0.113.10',
  kind: 'relay',
  error: null,
  all: {
    sent: 300, received: 297, loss_pct: 1, min_ms: 12, median_ms: 14, mean_ms: 14,
    p95_ms: 18, p99_ms: 22, max_ms: 30, stdev_ms: 2, jitter_ms: 1.5
  },
  idle: { p95_ms: 15 },
  busy: { p95_ms: 21 },
  samples: [[1, 12, 0.0, 'idle'], [2, 14, 0.2, 'idle']]
}

/** The same vintage, for an address that ignored the probes: the error carried the news. */
const oldSilent = {
  ip: '203.0.113.99',
  kind: 'isp-hop',
  error: 'no replies',
  all: {
    sent: 300, received: 0, loss_pct: null, min_ms: null, median_ms: null, mean_ms: null,
    p95_ms: null, p99_ms: null, max_ms: null, stdev_ms: null, jitter_ms: null
  },
  idle: { p95_ms: null },
  busy: { p95_ms: null },
  samples: []
}

/** A relay whose worst probe sits far above its p99, which is what a real long link does.
 *
 * Only the summary figures matter here, so the two samples are just enough to stop the run
 * being read as one that never answered.
 */
function spikySaoPaulo (min, p99, max) {
  return {
    analysis: {
      targets: {
        'sao-paulo': {
          silent: false,
          all: { sent: 300, received: 299, min_ms: min, p99_ms: p99, max_ms: max },
          samples: [[1, min, 0.0, 'idle'], [2, max, 0.2, 'idle']]
        }
      }
    }
  }
}

/** Floating point cannot promise an exact edge, so compare the ones that come out of it. */
function close (actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 1e-9,
    `${message}: expected ${expected}, got ${actual}`)
}

describe('isSilent', () => {
  it('trusts the flag when the record carries one', () => {
    assert.equal(isSilent(saoPauloSilent), true)
    assert.equal(isSilent(londonA), false)
  })

  it('falls back to no samples and no real error on a record saved before the flag', () => {
    assert.equal(isSilent(oldSilent), true)
    assert.equal(isSilent(oldMeasured), false)
  })

  it('does not call a genuine failure silent', () => {
    const broken = { error: 'ping: network is unreachable', all: {}, samples: [] }
    assert.equal(isSilent(broken), false)
  })

  it('is false for an address the run never probed', () => {
    assert.equal(isSilent(null), false)
    assert.equal(isSilent(undefined), false)
  })
})

describe('burstProbes', () => {
  it('counts the longest burst when the run recorded one', () => {
    assert.equal(burstProbes(londonA), 1)
  })

  it('gives zero, not null, for a run that counted bursts and lost nothing', () => {
    assert.strictEqual(burstProbes(londonB), 0)
  })

  it('gives null, not zero, for a run saved before bursts were counted', () => {
    // Never counted and counted zero are different answers, and the whole table
    // depends on telling them apart.
    assert.strictEqual(burstProbes(oldMeasured), null)
    assert.notStrictEqual(burstProbes(oldMeasured), 0)
  })

  it('gives null for an address that answers nothing', () => {
    assert.strictEqual(burstProbes(saoPauloSilent), null)
    assert.strictEqual(burstProbes(oldSilent), null)
  })
})

describe('lostCount', () => {
  it('is sent minus received', () => {
    assert.equal(lostCount(londonA), 1)
    assert.equal(lostCount(londonB), 0)
    assert.equal(lostCount(oldMeasured), 3)
  })

  it('is null for an address that answers nothing', () => {
    assert.strictEqual(lostCount(saoPauloSilent), null)
    assert.strictEqual(lostCount(oldSilent), null)
  })
})

describe('penalty', () => {
  it('is the busy p95 minus the idle p95, to one decimal', () => {
    assert.equal(penalty(londonA), 20)
    assert.equal(penalty(londonB), 10)
    assert.equal(penalty(oldMeasured), 6)
  })

  it('rounds to one decimal', () => {
    const entry = { silent: false, idle: { p95_ms: 19.44 }, busy: { p95_ms: 39.5 }, samples: [1] }
    assert.equal(penalty(entry), 20.1)
  })

  it('is null when either half is missing', () => {
    assert.strictEqual(penalty(saoPauloSilent), null)
    assert.strictEqual(penalty({ silent: false, idle: { p95_ms: 10 }, busy: {}, samples: [1] }), null)
  })
})

describe('liveTargets', () => {
  it('lists the answering targets in the order the tokens block gives', () => {
    // London answers in both runs, the router only in the second, Sao Paulo in neither.
    assert.deepEqual(liveTargets([runA, runB], TARGET_ORDER), ['router', 'london'])
  })

  it('drops a target that is silent in every run', () => {
    assert.deepEqual(liveTargets([runA], TARGET_ORDER), ['london'])
  })

  it('keeps a target the order list has never heard of, at the end', () => {
    const odd = { analysis: { targets: { frankfurt: londonB, london: londonA } } }
    assert.deepEqual(liveTargets([odd], TARGET_ORDER), ['london', 'frankfurt'])
  })

  it('is empty when nothing was measured', () => {
    assert.deepEqual(liveTargets([], TARGET_ORDER), [])
  })
})

describe('sharedBins', () => {
  it('spans the smaller best round trip to the larger p99 plus five percent', () => {
    // Run A: best 10 ms, p99 40 ms. Run B: best 50 ms, p99 80 ms.
    // So lo = 10, hi = 80 * 1.05 = 84, and four bins are 18.5 ms wide.
    const bins = sharedBins([runA, runB], 'london', 4)
    close(bins.lo, 10, 'lo')
    close(bins.hi, 84, 'hi')
    assert.equal(bins.edges.length, 5)
    const expected = [10, 28.5, 47, 65.5, 84]
    bins.edges.forEach((edge, i) => close(edge, expected[i], `edge ${i}`))
  })

  it('still stops at the worst p99, not the worst probe', () => {
    // The other half of the timeline range above: here the cut is the point. A histogram
    // stretched to a single 565 ms probe would squash every outline into the first bins,
    // and binCounts says out loud that what sits above the top is dropped.
    const bins = sharedBins([spikySaoPaulo(202, 355.36, 379),
      spikySaoPaulo(195, 453.08, 565)], 'sao-paulo', 4)
    close(bins.lo, 195, 'lo')
    close(bins.hi, 453.08 * 1.05, 'hi')
  })

  it('ignores a run whose target is silent', () => {
    // Only run A is asked about Sao Paulo, and it never answered there.
    assert.strictEqual(sharedBins([runA], 'sao-paulo', 4), null)
  })

  it('is null when no run measured the target at all', () => {
    assert.strictEqual(sharedBins([runA, runB], 'madrid', 4), null)
  })
})

describe('binCounts', () => {
  const bins = { lo: 0, hi: 100, edges: [0, 25, 50, 75, 100] }
  const run = {
    analysis: {
      targets: {
        london: {
          silent: false,
          all: { sent: 7, received: 7 },
          samples: [[1, 0, 0.0, 'idle'], [2, 10, 0.2, 'idle'], [3, 25, 0.4, 'idle'],
            [4, 50, 0.6, 'idle'], [5, 60, 0.8, 'idle'], [6, 100, 1.0, 'idle'],
            [7, 101, 1.2, 'idle']]
        }
      }
    }
  }

  it('puts a sample on an interior edge in the lower bin and one at hi in the last', () => {
    // 0 and 10 and 25 fall in the first bin (25 sits on its top edge), 50 in the second
    // (again its top edge), 60 in the third, 100 in the last, and 101 is above hi.
    assert.deepEqual(binCounts(run, 'london', bins), [3, 1, 1, 1])
  })

  it('drops only what sits above hi', () => {
    const counted = binCounts(run, 'london', bins).reduce((a, b) => a + b, 0)
    assert.equal(counted, 6)
  })

  it('splits the two runs across the bins they share', () => {
    // Bins 10 to 84 in four steps of 18.5: 10-28.5, 28.5-47, 47-65.5, 65.5-84.
    const shared = sharedBins([runA, runB], 'london', 4)
    assert.deepEqual(binCounts(runA, 'london', shared), [2, 2, 0, 0])
    assert.deepEqual(binCounts(runB, 'london', shared), [0, 0, 2, 2])
  })

  it('spreads all three runs over one shared set of bins', () => {
    // Same bins as above: run C's 30, 32, 36 and 42 ms all land in the second one.
    const shared = sharedBins([runA, runB, runC], 'london', 4)
    close(shared.hi, 84, 'hi')
    assert.deepEqual(binCounts(runA, 'london', shared), [2, 2, 0, 0])
    assert.deepEqual(binCounts(runC, 'london', shared), [0, 4, 0, 0])
    assert.deepEqual(binCounts(runB, 'london', shared), [0, 0, 2, 2])
  })

  it('gives a row of zeros for a run that never probed the target', () => {
    assert.deepEqual(binCounts(runB, 'sao-paulo', bins), [0, 0, 0, 0])
  })
})

describe('sharedYRange', () => {
  it('covers every run worst round trip with slack, rounded outwards to a readable step', () => {
    // lo = 10 * 0.95 = 9.5, hi = 80 * 1.05 = 84, so the span is 74.5 and the step is 20.
    assert.deepEqual(sharedYRange([runA, runB], 'london'), [0, 100])
  })

  it('reaches the worst probe, not the p99, so the page hides nothing', () => {
    // The page pins this range onto the timeline panels, so a probe above it is drawn
    // nowhere at all. These are the real Sao Paulo figures of the two Leeds runs in the
    // log: leeds_bt_2026-08-30T15-32-20Z peaked at 565 ms against a p99 of 453, and a
    // range built from p99 stopped at 500 and swallowed two of its 299 probes.
    const [lo, hi] = sharedYRange([spikySaoPaulo(202, 355.36, 379),
      spikySaoPaulo(195, 453.08, 565)], 'sao-paulo')
    assert.ok(hi >= 565, `the worst probe was 565 ms and the range stops at ${hi}`)
    assert.deepEqual([lo, hi], [100, 600])
  })

  it('does not drag the floor to zero for a distant relay', () => {
    // lo = 200 * 0.95 = 190, hi = 260 * 1.05 = 273, span 83, step 20: 180 to 280.
    const distant = {
      analysis: {
        targets: {
          'sao-paulo': {
            silent: false,
            all: { sent: 2, received: 2, min_ms: 200, p99_ms: 260, max_ms: 260 },
            samples: [[1, 200, 0.0, 'idle'], [2, 260, 0.2, 'idle']]
          }
        }
      }
    }
    assert.deepEqual(sharedYRange([distant], 'sao-paulo'), [180, 280])
  })

  it('is null when no run measured the target', () => {
    assert.strictEqual(sharedYRange([runA], 'madrid'), null)
  })
})

describe('diffRows', () => {
  const rows = diffRows([runA, runB], 'london')
  const byLabel = Object.fromEntries(rows.map((row) => [row.label, row]))

  it('keeps the row order the page expects', () => {
    assert.deepEqual(rows.map((row) => row.label), [
      'loss %', 'probes lost', 'longest burst', 'best ms', 'median ms', 'p95 ms', 'p99 ms',
      'jitter ms', 'under-load penalty ms', 'download Mbit/s', 'upload Mbit/s',
      'local overhead ms'
    ])
  })

  it('reads one value per run off the record', () => {
    assert.deepEqual(byLabel['loss %'].values, [20, 0])
    assert.deepEqual(byLabel['probes lost'].values, [1, 0])
    assert.deepEqual(byLabel['longest burst'].values, [1, 0])
    assert.deepEqual(byLabel['best ms'].values, [10, 50])
    assert.deepEqual(byLabel['median ms'].values, [25, 65])
    assert.deepEqual(byLabel['p95 ms'].values, [38.5, 78.5])
    assert.deepEqual(byLabel['p99 ms'].values, [40, 80])
    assert.deepEqual(byLabel['jitter ms'].values, [10, 10])
    assert.deepEqual(byLabel['under-load penalty ms'].values, [20, 10])
    assert.deepEqual(byLabel['download Mbit/s'].values, [44.3, 175.1])
    assert.deepEqual(byLabel['upload Mbit/s'].values, [63.4, 224.2])
    assert.deepEqual(byLabel['local overhead ms'].values, [1.2, 0.8])
  })

  it('marks the lower value best for latency and loss', () => {
    assert.equal(byLabel['loss %'].bestIndex, 1)
    assert.equal(byLabel['probes lost'].bestIndex, 1)
    assert.equal(byLabel['longest burst'].bestIndex, 1)
    assert.equal(byLabel['best ms'].bestIndex, 0)
    assert.equal(byLabel['median ms'].bestIndex, 0)
    assert.equal(byLabel['p95 ms'].bestIndex, 0)
    assert.equal(byLabel['p99 ms'].bestIndex, 0)
    assert.equal(byLabel['under-load penalty ms'].bestIndex, 1)
    assert.equal(byLabel['local overhead ms'].bestIndex, 1)
  })

  it('marks the higher value best for download and upload', () => {
    assert.equal(byLabel['download Mbit/s'].bestIndex, 1)
    assert.equal(byLabel['upload Mbit/s'].bestIndex, 1)
  })

  it('marks nothing when the two runs tie', () => {
    // Both runs jittered by 10 ms, so neither of them won.
    assert.strictEqual(byLabel['jitter ms'].bestIndex, null)
  })

  it('marks nothing when only one run has the figure', () => {
    const noLondon = { speed: [], analysis: { local_overhead_ms: 0.9, targets: {} } }
    const lonely = diffRows([runA, noLondon], 'london')
    const best = lonely.find((row) => row.label === 'best ms')
    assert.deepEqual(best.values, [10, null])
    assert.strictEqual(best.bestIndex, null)
  })

  it('picks one winner out of three runs, and none when the best two are equal', () => {
    // Three is the most the page ever ticks, and a winner in the middle slot is the case
    // an off-by-one would hide.
    const three = diffRows([runA, runB, runC], 'london')
    const label = Object.fromEntries(three.map((row) => [row.label, row]))
    assert.deepEqual(label['best ms'].values, [10, 50, 30])
    assert.equal(label['best ms'].bestIndex, 0)
    assert.deepEqual(label['under-load penalty ms'].values, [20, 10, 5])
    assert.equal(label['under-load penalty ms'].bestIndex, 2)
    assert.deepEqual(label['jitter ms'].values, [10, 10, 4])
    assert.equal(label['jitter ms'].bestIndex, 2)
    assert.deepEqual(label['download Mbit/s'].values, [44.3, 175.1, 200])
    assert.equal(label['download Mbit/s'].bestIndex, 2)
    assert.deepEqual(label['upload Mbit/s'].values, [63.4, 224.2, 100])
    assert.equal(label['upload Mbit/s'].bestIndex, 1)
    // Runs B and C both lost nothing, so neither of them is the better one.
    assert.deepEqual(label['loss %'].values, [20, 0, 0])
    assert.strictEqual(label['loss %'].bestIndex, null)
    assert.deepEqual(label['probes lost'].values, [1, 0, 0])
    assert.strictEqual(label['probes lost'].bestIndex, null)
  })

  it('carries the decimal places each row is written with', () => {
    assert.equal(byLabel['loss %'].nd, 1)
    assert.equal(byLabel['probes lost'].nd, 0)
    assert.equal(byLabel['longest burst'].nd, 0)
    assert.equal(byLabel['median ms'].nd, 1)
    assert.equal(byLabel['download Mbit/s'].nd, 1)
  })

  it('leaves a silent target with no figures but keeps the run-wide ones', () => {
    const silentRows = diffRows([runA], 'sao-paulo')
    const label = Object.fromEntries(silentRows.map((row) => [row.label, row]))
    assert.deepEqual(label['loss %'].values, [null])
    assert.deepEqual(label['probes lost'].values, [null])
    assert.deepEqual(label['longest burst'].values, [null])
    assert.deepEqual(label['median ms'].values, [null])
    assert.deepEqual(label['download Mbit/s'].values, [44.3])
  })
})
