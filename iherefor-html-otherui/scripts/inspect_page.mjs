#!/usr/bin/env node
/* Read-only page inspection helper. Requires Playwright (npm i playwright). */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const fs = require('fs');
const path = require('path');
const input = path.resolve(process.argv[process.argv.indexOf('--input') + 1] || '.');
const out = path.resolve(process.argv[process.argv.indexOf('--output') + 1] || path.join(process.cwd(), 'page-inspection.json'));
let playwright; try { playwright = require('playwright'); } catch (_) { console.error('inspect_page: Playwright is required. Install it in the skill runtime with: npm install playwright'); process.exit(1); }
(async () => {
  const entry = fs.statSync(input).isDirectory() ? path.join(input, 'index.html') : input;
  const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined;
  const browser = await playwright.chromium.launch({ headless: true, executablePath });
  const page = await browser.newPage({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2 });
  await page.goto(`file://${entry}`, { waitUntil: 'load' });
  const result = await page.evaluate(() => ({ url: location.href, title: document.title, bodyText: document.body.innerText, htmlLang: document.documentElement.lang || null, links: Array.from(document.querySelectorAll('link')).map(x => ({ rel:x.rel, href:x.href })), scripts: Array.from(document.scripts).map(x => x.src || 'inline'), interactive: Array.from(document.querySelectorAll('a,button,input,select,textarea,[role="button"],[onclick],[tabindex]')).map((e,i) => ({ index:i, tag:e.tagName.toLowerCase(), text:(e.innerText||e.value||'').trim(), id:e.id||null, ariaLabel:e.getAttribute('aria-label'), rect:(() => { const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; })() })) }));
  fs.writeFileSync(out, JSON.stringify(result, null, 2)); await browser.close(); console.log(out);
})().catch(e => { console.error(`inspect_page: ${e.message}`); process.exit(1); });
