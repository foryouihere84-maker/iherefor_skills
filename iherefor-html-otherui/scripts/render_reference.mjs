#!/usr/bin/env node
/* Deterministic Lanhu HTML renderer. Requires Playwright (npm i playwright). */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const fs = require('fs');
const path = require('path');

/* 动画/过渡会破坏截图的确定性，渲染前必须禁用；该 CSS 会在导航之后注入。 */
const STABILIZE_CSS = '*,:before,:after{animation:none!important;transition:none!important;caret-color:transparent!important}';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
function viewport(value) {
  const m = String(value).match(/^(\d+)x(\d+)$/);
  if (!m) throw new Error(`Invalid --viewport: ${value}; expected WIDTHxHEIGHT`);
  return { width: Number(m[1]), height: Number(m[2]) };
}
async function main() {
  let playwright;
  try { playwright = require('playwright'); }
  catch (_) { throw new Error('Playwright is required. Install it with: npm install playwright'); }
  const input = path.resolve(arg('--input', '.'));
  const output = path.resolve(arg('--output', path.join(process.cwd(), 'reference')));
  const entry = fs.statSync(input).isDirectory() ? path.join(input, 'index.html') : input;
  if (!fs.existsSync(entry)) throw new Error(`HTML entry not found: ${entry}`);
  fs.mkdirSync(output, { recursive: true });
  const vp = viewport(arg('--viewport', '393x852'));
  const scale = Number(arg('--scale', '2'));
  const executablePath = arg('--executable', process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined);
  const browser = await playwright.chromium.launch({ headless: true, executablePath });
  const context = await browser.newContext({ viewport: vp, deviceScaleFactor: scale, reducedMotion: 'reduce', locale: arg('--locale', 'en-US'), timezoneId: arg('--timezone', 'Asia/Shanghai') });
  const consoleMessages = [], failedRequests = [];
  const page = await context.newPage();
  page.on('console', m => consoleMessages.push({ type: m.type(), text: m.text() }));
  page.on('requestfailed', r => failedRequests.push({ url: r.url(), error: r.failure() && r.failure().errorText }));
  await page.goto(`file://${entry}`, { waitUntil: 'load' });
  /* addStyleTag 只作用于「当前文档」：若在 goto 之前调用，样式会随 about:blank 一起被丢弃。 */
  await page.addStyleTag({ content: STABILIZE_CSS });
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await Promise.all(Array.from(document.images).map(i => i.complete ? Promise.resolve() : new Promise(r => { i.addEventListener('load', r, { once: true }); i.addEventListener('error', r, { once: true }); })));
  });
  await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
  /* 注入后当场回读 DOM，把「样式确实生效」记录成页面事实，而不是脚本的自我声明。 */
  const styleInjection = await page.evaluate((css) => {
    const styles = Array.from(document.querySelectorAll('style'));
    const first = document.querySelector('body *');
    return {
      css,
      presentInDom: styles.some(s => (s.textContent || '').includes('animation:none')),
      styleTagCount: styles.length,
      firstElementAnimationName: first ? getComputedStyle(first).animationName : null,
    };
  }, STABILIZE_CSS);
  await page.screenshot({ path: path.join(output, 'reference.png'), fullPage: true });
  const facts = await page.evaluate(() => {
    const visible = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
    const elements = Array.from(document.querySelectorAll('body *')).filter(visible).map((e, index) => {
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      return { index, tag: e.tagName.toLowerCase(), id: e.id || null, className: typeof e.className === 'string' ? e.className : null, text: (e.innerText || '').trim().slice(0, 300), rect: { x:r.x, y:r.y, width:r.width, height:r.height }, style: { display:s.display, position:s.position, zIndex:s.zIndex, overflow:s.overflow, color:s.color, backgroundColor:s.backgroundColor, backgroundImage:s.backgroundImage, fontFamily:s.fontFamily, fontSize:s.fontSize, fontWeight:s.fontWeight, lineHeight:s.lineHeight, borderRadius:s.borderRadius, boxShadow:s.boxShadow, opacity:s.opacity, transform:s.transform }, role:e.getAttribute('role'), ariaLabel:e.getAttribute('aria-label'), src:e.tagName === 'IMG' ? e.currentSrc || e.src : null };
    });
    return { title: document.title, url: location.href, viewport: { width: innerWidth, height: innerHeight, devicePixelRatio: devicePixelRatio }, documentSize: { width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight }, elements };
  });
  const meta = { schemaVersion: 1, entry, viewport: vp, scale, browser: await browser.version(), capturedAt: new Date().toISOString(), styleInjection, console: consoleMessages, failedRequests, fonts: await page.evaluate(() => Array.from(document.fonts || []).map(f => ({ family:f.family, status:f.status, weight:f.weight, style:f.style }))), images: await page.evaluate(() => Array.from(document.images).map(i => ({ src:i.currentSrc || i.src, complete:i.complete, naturalWidth:i.naturalWidth, naturalHeight:i.naturalHeight }))) };
  fs.writeFileSync(path.join(output, 'page-facts.json'), JSON.stringify(facts, null, 2));
  fs.writeFileSync(path.join(output, 'browser-meta.json'), JSON.stringify(meta, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, screenshot: path.join(output, 'reference.png'), facts: path.join(output, 'page-facts.json'), meta: path.join(output, 'browser-meta.json') }, null, 2));
}
main().catch(e => { console.error(`render_reference: ${e.message}`); process.exit(1); });
