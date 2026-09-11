#!/usr/bin/env node
/* Read-only page inspection helper. Requires Playwright (npm i playwright).

只读取运行中的页面并输出摘要，不修改任何文件。viewport 与 scale 应与基准渲染一致：
默认值只是应急兜底，正式流程请用 --viewport-from 指向本次 run 的 runtime-device.json。
*/
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const fs = require('fs');
const path = require('path');

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function parseViewport(value) {
  const m = String(value).match(/^(\d+)x(\d+)$/);
  if (!m) throw new Error(`Invalid --viewport: ${value}; expected WIDTHxHEIGHT`);
  return { width: Number(m[1]), height: Number(m[2]) };
}

const input = path.resolve(arg('--input', '.'));
const out = path.resolve(arg('--output', path.join(process.cwd(), 'page-inspection.json')));
const viewportFile = arg('--viewport-from', null);

let viewport;
let scale;
let viewportSource;
if (viewportFile) {
  const device = JSON.parse(fs.readFileSync(path.resolve(viewportFile), 'utf8'));
  const points = device.screenBoundsPoints;
  if (!points || !points.width || !points.height) throw new Error(`--viewport-from 缺少 screenBoundsPoints: ${viewportFile}`);
  viewport = { width: Math.round(points.width), height: Math.round(points.height) };
  scale = Number(device.screenshotScale || 1);
  viewportSource = `runtime-device:${path.resolve(viewportFile)}`;
} else {
  viewport = parseViewport(arg('--viewport', '393x852'));
  scale = Number(arg('--scale', '2'));
  viewportSource = 'cli';
}

let playwright; try { playwright = require('playwright'); } catch (_) { console.error('inspect_page: Playwright is required. Install it with: npm install playwright'); process.exit(1); }
(async () => {
  const entry = fs.statSync(input).isDirectory() ? path.join(input, 'index.html') : input;
  const executablePath = arg('--executable', process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined);
  const browser = await playwright.chromium.launch({ headless: true, executablePath });
  const page = await browser.newPage({ viewport, deviceScaleFactor: scale });
  await page.goto(`file://${entry}`, { waitUntil: 'load' });
  const result = await page.evaluate(() => ({ url: location.href, title: document.title, bodyText: document.body.innerText, htmlLang: document.documentElement.lang || null, links: Array.from(document.querySelectorAll('link')).map(x => ({ rel:x.rel, href:x.href })), scripts: Array.from(document.scripts).map(x => x.src || 'inline'), interactive: Array.from(document.querySelectorAll('a,button,input,select,textarea,[role="button"],[onclick],[tabindex]')).map((e,i) => ({ index:i, tag:e.tagName.toLowerCase(), text:(e.innerText||e.value||'').trim(), id:e.id||null, ariaLabel:e.getAttribute('aria-label'), rect:(() => { const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; })() })) }));
  result.viewport = viewport;
  result.scale = scale;
  result.viewportSource = viewportSource;
  fs.writeFileSync(out, JSON.stringify(result, null, 2)); await browser.close(); console.log(out);
})().catch(e => { console.error(`inspect_page: ${e.message}`); process.exit(1); });
