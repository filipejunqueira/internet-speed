// The walk that produced this folder's screenshots, 2026-09-24. Run from Claude's container:
// the Playwright library comes from the global @playwright/cli package, and it asks for
// Chromium build 1243 while the cache holds 1234, so the browser is launched by path.
// It writes 7 states x 3 views into <outdir>, one PNG per page and one per <section>.
// Walk the published site headless: screenshots per state, notes text, console errors.
// usage: node walk.mjs <outdir> [base]
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.HOME +
  '/.npm-global/lib/node_modules/@playwright/cli/node_modules/playwright')

const out = process.argv[2] || 'shots'
const BASE = process.argv[3] || 'https://filipejunqueira.github.io/internet-speed-reports/'
mkdirSync(out, { recursive: true })
const R1359 = 'leeds_bt_2026-08-30T13-59-15Z'
const R1515 = 'leeds_bt_2026-08-30T15-15-01Z'
const R1532 = 'leeds_bt_2026-08-30T15-32-20Z'
const R0903 = '2026-09-03T13-14-53Z'
const bust = `t=${Date.now()}`

const states = [
  { name: 'index', url: `?${bust}` },
  { name: 'one-1359', url: `?runs=${R1359}&${bust}` },
  { name: 'two-1359-1532-sp', url: `?runs=${R1359},${R1532}&target=sao-paulo&${bust}` },
  { name: 'three-leeds-sp', url: `?runs=${R1359},${R1515},${R1532}&target=sao-paulo&${bust}` },
  { name: 'three-mixed-london', url: `?runs=${R0903},${R1532},${R1359}&target=london&${bust}` },
  { name: 'report-1359', url: `runs/${R1359}.html?${bust}` },
  { name: 'report-0903', url: `runs/${R0903}.html?${bust}` },
]
const views = [
  { tag: 'desk', viewport: { width: 1280, height: 900 }, colorScheme: 'light' },
  { tag: 'desk-dark', viewport: { width: 1280, height: 900 }, colorScheme: 'dark' },
  { tag: 'phone', viewport: { width: 390, height: 844 }, colorScheme: 'light', isMobile: true },
]
const only = (process.env.ONLY || '').split(',').filter(Boolean)
const onlyViews = (process.env.VIEWS || '').split(',').filter(Boolean)

const browser = await chromium.launch({ executablePath: process.env.HOME +
  '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome' })
const report = {}
for (const view of views) {
  if (onlyViews.length && !onlyViews.includes(view.tag)) continue
  const ctx = await browser.newContext({ viewport: view.viewport, colorScheme: view.colorScheme,
    isMobile: !!view.isMobile, deviceScaleFactor: 1 })
  for (const st of states) {
    if (only.length && !only.includes(st.name)) continue
    const page = await ctx.newPage()
    const errors = []
    page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()) })
    page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
    page.on('response', (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`) })
    await page.goto(BASE + st.url, { waitUntil: 'networkidle', timeout: 90000 })
    await page.waitForTimeout(2500) // plotly draws after load
    const key = `${st.name}.${view.tag}`
    await page.screenshot({ path: `${out}/${key}.full.png`, fullPage: true })
    const info = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth
      const notes = [...document.querySelectorAll('.note')].map((n) => ({
        text: n.textContent.trim().slice(0, 600),
        color: getComputedStyle(n).color, size: getComputedStyle(n).fontSize,
        style: getComputedStyle(n).fontStyle }))
      const heads = [...document.querySelectorAll('h1,h2,h3')].map((h) => h.tagName + ' ' +
        h.textContent.trim().slice(0, 80))
      const sections = [...document.querySelectorAll('section')].length
      const frames = [...document.querySelectorAll('iframe')].map((f) => ({ src: f.src,
        h: f.getBoundingClientRect().height }))
      return { docW, winW: innerWidth, docH: document.documentElement.scrollHeight, notes,
        heads, sections, frames, title: document.title }
    })
    // each section on its own, so a long page can still be read at full size
    const secs = await page.$$('section')
    for (let i = 0; i < secs.length; i++) {
      const box = await secs[i].boundingBox()
      if (!box || box.height < 20) continue
      await secs[i].screenshot({ path: `${out}/${key}.s${String(i).padStart(2, '0')}.png` })
    }
    // a report inside the explorer's frame: read its notes too
    const frame = page.frames().find((f) => f !== page.mainFrame() && f.url().includes('runs/'))
    if (frame) {
      info.frameNotes = await frame.evaluate(() => [...document.querySelectorAll('.note')]
        .map((n) => n.textContent.trim().slice(0, 400)))
    }
    info.errors = errors
    report[key] = info
    await page.close()
  }
  await ctx.close()
}
await browser.close()
writeFileSync(`${out}/report.json`, JSON.stringify(report, null, 1))
console.log(JSON.stringify(report, null, 1))
