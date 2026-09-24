// Measure the contrast of every piece of text in every chart, and of every caption, in
// light and dark mode. Colours come from the computed styles; the ratio is WCAG's.
// usage: node contrast.mjs [base]   (default: the live site). Same browser setup as walk.mjs.
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.HOME +
  '/.npm-global/lib/node_modules/@playwright/cli/node_modules/playwright')

const BASE = process.argv[2] || 'https://filipejunqueira.github.io/internet-speed-reports/'
const R1359 = 'leeds_bt_2026-08-30T13-59-15Z'
const pages = [
  ['explorer, three Leeds runs, São Paulo',
    `?runs=${R1359},leeds_bt_2026-08-30T15-15-01Z,leeds_bt_2026-08-30T15-32-20Z&target=sao-paulo`],
  ['explorer, three runs, London', `?runs=2026-09-03T13-14-53Z,${R1359}&target=london`],
  ['report 13:59', `runs/${R1359}.html`],
  ['report 2026-09-03', 'runs/2026-09-03T13-14-53Z.html'],
]

function lum([r, g, b]) {
  const c = [r, g, b].map((v) => v / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const rgb = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number)
function ratio(a, b) {
  const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

const browser = await chromium.launch({ executablePath: process.env.HOME +
  '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome' })
let worst = Infinity
for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({ colorScheme: scheme, viewport: { width: 1280, height: 900 } })
  for (const [name, url] of pages) {
    const page = await ctx.newPage()
    await page.goto(BASE + url + (url.includes('?') ? '&' : '?') + `t=${Date.now()}`,
      { waitUntil: 'networkidle', timeout: 90000 })
    await page.waitForTimeout(2500)
    const found = await page.evaluate(() => {
      const bg = (el) => {
        for (let e = el; e; e = e.parentElement) {
          const c = getComputedStyle(e).backgroundColor
          if (c && !c.startsWith('rgba(0, 0, 0, 0)') && c !== 'transparent') return c
        }
        return getComputedStyle(document.body).backgroundColor
      }
      const charts = [...document.querySelectorAll('.js-plotly-plot svg text')]
        .filter((t) => t.textContent.trim() && t.getBoundingClientRect().width > 0)
        .map((t) => ({ kind: t.closest('.geo, .geolayer, .scattergeolayer') ? 'map' : 'chart',
          text: t.textContent.trim().slice(0, 40), fg: getComputedStyle(t).fill,
          bg: bg(t.closest('.js-plotly-plot')) }))
      const captions = [...document.querySelectorAll('.note, .hint, .foot, .sub, summary, .ip')]
        .filter((t) => t.textContent.trim() && t.getBoundingClientRect().width > 0)
        .map((t) => ({ kind: 'caption', text: t.textContent.trim().slice(0, 40),
          fg: getComputedStyle(t).color, bg: bg(t) }))
      return [...charts, ...captions]
    })
    const byKind = {}
    for (const f of found) {
      f.ratio = ratio(f.fg, f.bg)
      ;(byKind[f.kind] ||= []).push(f)
    }
    for (const [kind, list] of Object.entries(byKind)) {
      list.sort((a, b) => a.ratio - b.ratio)
      const low = list[0]
      if (kind !== 'map') worst = Math.min(worst, low.ratio)
      console.log(`${scheme.padEnd(5)} ${name.padEnd(38)} ${kind.padEnd(7)} n=${String(list.length).padStart(3)}` +
        `  lowest ${low.ratio.toFixed(2)}:1  "${low.text}" ${low.fg} on ${low.bg}`)
    }
    await page.close()
  }
  await ctx.close()
}
await browser.close()
console.log(`lowest outside the map: ${worst.toFixed(2)}:1`)
