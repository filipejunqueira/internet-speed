// Tick the three Leeds runs with one run's numbers blocked, and print the sentence that names
// the run that would not load, beside the names the rest of the page uses.
// usage: node failed-load.mjs [base]   Same browser setup as walk.mjs.
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.HOME +
  '/.npm-global/lib/node_modules/@playwright/cli/node_modules/playwright')

const BASE = process.argv[2] || 'https://filipejunqueira.github.io/internet-speed-reports/'
const BLOCKED = 'leeds_bt_2026-08-30T15-15-01Z'
const browser = await chromium.launch({ executablePath: process.env.HOME +
  '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome' })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
await page.route(`**/runs/${BLOCKED}.json*`, (route) => route.abort())
await page.goto(`${BASE}?runs=leeds_bt_2026-08-30T13-59-15Z,${BLOCKED},leeds_bt_2026-08-30T15-32-20Z` +
  `&target=sao-paulo&t=${Date.now()}`, { waitUntil: 'networkidle', timeout: 90000 })
await page.waitForTimeout(2500)
const found = await page.evaluate(() => ({
  failed: [...document.querySelectorAll('.note')].map((n) => n.textContent)
    .filter((t) => t.includes('would not load')),
  tiles: [...document.querySelectorAll('.runs .run .name')].map((t) => t.textContent.trim()),
}))
console.log(JSON.stringify(found, null, 1))
await browser.close()
