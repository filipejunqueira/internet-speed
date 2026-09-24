// List every pair of text boxes that overlap inside one chart, on the explorer and the report
// pages, at desktop and phone width. Also reports how much of the map's box the map fills.
// usage: node overlaps.mjs [base]   (default: the live site). Same browser setup as walk.mjs.
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.HOME +
  '/.npm-global/lib/node_modules/@playwright/cli/node_modules/playwright')

const BASE = process.argv[2] || 'https://filipejunqueira.github.io/internet-speed-reports/'
const R1359 = 'leeds_bt_2026-08-30T13-59-15Z'
const R1515 = 'leeds_bt_2026-08-30T15-15-01Z'
const R1532 = 'leeds_bt_2026-08-30T15-32-20Z'
const R0903 = '2026-09-03T13-14-53Z'
const pages = [
  ['three Leeds, São Paulo', `?runs=${R1359},${R1515},${R1532}&target=sao-paulo`],
  ['three Leeds, London', `?runs=${R1359},${R1515},${R1532}&target=london`],
  ['three mixed, US-East', `?runs=${R0903},${R1532},${R1359}&target=us-east`],
  ['two, Madrid', `?runs=${R0903},${R1359}&target=madrid`],
  ['report 13:59', `runs/${R1359}.html`],
  ['report 2026-09-03', `runs/${R0903}.html`],
]
const widths = [['desk', 1280], ['phone', 390]]
// ONLY=report,Leeds keeps the states whose name contains any of those words, for a quick look
const only = (process.env.ONLY || '').split(',').filter(Boolean)
// A text box is taller than its letters, so two boxes can graze by a pixel or two with no
// ink touching: measured 1.3-2.0 px for a legend under a title. Real collisions measured
// 11-14 px. Count only an overlap at least this wide and this tall.
const MIN_SIDE = 3 // px

const browser = await chromium.launch({ executablePath: process.env.HOME +
  '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome' })
let total = 0
let dupes = 0
let failed = 0
for (const [tag, width] of widths) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, isMobile: tag === 'phone' })
  for (const [name, url] of pages) {
    if (only.length && !only.some((w) => name.includes(w))) continue
    const page = await ctx.newPage()
    await page.goto(BASE + url + (url.includes('?') ? '&' : '?') + `t=${Date.now()}`,
      { waitUntil: 'networkidle', timeout: 90000 })
    await page.waitForTimeout(2500)
    const found = await page.evaluate((minSide) => {
      const out = { pairs: [], maps: [] }
      for (const fig of document.querySelectorAll('.js-plotly-plot')) {
        const card = fig.closest('section')
        const heading = ((card && card.querySelector('h2, h3, .ctitle')) || {}).textContent || fig.id
        const boxes = [...fig.querySelectorAll('svg text')]
          .filter((t) => t.textContent.trim())
          .map((t) => ({ text: t.textContent.trim().slice(0, 30), r: t.getBoundingClientRect(),
            where: t.closest('.legend') ? 'legend' : t.closest('.annotation') ? 'annotation'
              : t.closest('.xtick, .ytick') ? 'tick' : t.closest('.g-xtitle, .g-ytitle') ? 'axis title'
              : t.closest('.g-gtitle') ? 'title' : 'mark' }))
          .filter((b) => b.r.width > 0 && b.r.height > 0)
        for (let i = 0; i < boxes.length; i++) {
          for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i].r, b = boxes[j].r
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left)
            const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
            if (w >= minSide && h >= minSide) {
              out.pairs.push({ heading: heading.trim().slice(0, 40),
                a: `${boxes[i].where} "${boxes[i].text}"`, b: `${boxes[j].where} "${boxes[j].text}"`,
                area: Math.round(w * h) })
            }
          }
        }
        const geo = fig.querySelector('.geo .bg, .geolayer .bg')
        if (geo) {
          const g = geo.getBoundingClientRect(), f = fig.getBoundingClientRect()
          // A legend under the map is the box doing its job, not blank space, so it counts
          // with the map; one drawn over the map is already inside the map's height.
          const legend = fig.querySelector('.legend')
          const l = legend && legend.getBoundingClientRect()
          const beside = l && (l.top >= g.bottom - 1 || l.bottom <= g.top + 1) ? l.height : 0
          out.maps.push({ heading: heading.trim().slice(0, 40), map: Math.round(g.height + beside),
            box: Math.round(f.height), share: +((g.height + beside) / f.height).toFixed(2) })
        }
      }
      // Names a reader uses to tell runs apart: each chart's legend, the run tiles, the
      // timeline titles, the comparison table's heads and the map caption. A name shown twice in one of these says nothing about which is which.
      const groups = [...document.querySelectorAll('.js-plotly-plot')]
        .map((fig) => [...fig.querySelectorAll('.legendtext')].map((t) => t.textContent.trim()))
      groups.push([...document.querySelectorAll('.runs .run .name')].map((t) => t.textContent.trim()))
      groups.push([...document.querySelectorAll('.ctitle')].map((t) => t.textContent.trim()))
      // the comparison table's column heads, less the first, which names the target
      groups.push([...document.querySelectorAll('.diff thead th')].slice(1).map((t) => t.textContent.trim()))
      // the map caption names a run before each route-date sentence: "leeds_bt: Traced on …"
      for (const note of document.querySelectorAll('.note')) {
        const named = [...note.textContent.matchAll(/(?:^|\.\s)([^.]*?): (?:Traced on|When this route)/g)]
        if (named.length) groups.push(named.map((m) => m[1].trim()))
      }
      out.dupes = groups.reduce((n, g) => n + g.length - new Set(g).size, 0)
      out.charts = document.querySelectorAll('.js-plotly-plot').length
      return out
    }, MIN_SIDE)
    total += found.pairs.length
    dupes += found.dupes
    // A page that did not draw has nothing to overlap, so it would read as a clean 0.
    if (!found.charts) { failed += 1; console.log(`${tag.padEnd(5)} ${name.padEnd(24)} DID NOT DRAW`); await page.close(); continue }
    console.log(`${tag.padEnd(5)} ${name.padEnd(24)} overlaps=${found.pairs.length} repeated names=${found.dupes}` +
      found.maps.map((m) => `  map ${m.map}/${m.box} px (${m.share})`).join(''))
    // one line per kind of collision on this page, with how many figures repeat it
    const kinds = new Map()
    for (const p of found.pairs) {
      const kind = `[${p.heading.replace(/ \d.*$/, '')}] ` +
        [p.a, p.b].map((s) => s.replace(/"[^"]*"/, (m) => /\d/.test(m) ? '"…"' : m)).join('  x  ')
      kinds.set(kind, (kinds.get(kind) || 0) + 1)
    }
    for (const [kind, n] of kinds) console.log(`        ${String(n).padStart(3)}×  ${kind}`)
    await page.close()
  }
  await ctx.close()
}
await browser.close()
console.log(`overlapping pairs in total: ${total}; repeated names in total: ${dupes}` +
  (failed ? `; ${failed} page(s) DID NOT DRAW, so these totals are not a result` : ''))
if (failed) process.exitCode = 1
