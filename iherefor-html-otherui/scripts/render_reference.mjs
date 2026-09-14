#!/usr/bin/env node
/* Deterministic Lanhu HTML renderer. Requires Playwright (npm i playwright).

产出三件套（都是「基准」，写入页面级 reference/）：
  reference.png    视口截图，像素尺寸 = 设备点尺寸 x screenshotScale
  page-facts.json  schema v2：每个可见元素的 DOM rect **以及它在 reference.png 里的像素
                   rect**、文本度量、实际命中字体、渐变/阴影等 computed style
  browser-meta.json 浏览器版本、viewport、字体解析结果、console/network

关键点：page-facts 里的 `rectInReference` 是「元素在基准图里应该出现在哪」的唯一
客观量。历史上只有 DOM rect（CSS px）而没有图片像素 rect，于是「基准图与 DOM 不符」
这件事没有任何断言能发现——尺寸校验只看 PNG 尺寸，尺寸相等就全绿。
*/
import { createRequire } from 'module';
import { launchChromium } from './browser-launch.mjs';
import { alphaBounds } from './png_bounds.mjs';
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
/* 基准图必须与目标设备截图同源：点尺寸取自运行时 API，scale 取自截图像素比。 */
function viewportFromRuntimeDevice(file) {
  const payload = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8'));
  const points = payload.screenBoundsPoints;
  if (!points || !points.width || !points.height) {
    throw new Error(`--viewport-from 缺少 screenBoundsPoints: ${file}`);
  }
  const scale = Number(payload.screenshotScale || 1);
  if (!(scale > 0)) throw new Error(`--viewport-from 的 screenshotScale 非法: ${payload.screenshotScale}`);
  return { viewport: { width: Math.round(points.width), height: Math.round(points.height) }, scale };
}

/* 页面里跑的两段采集逻辑必须共用**同一套判定**和**同一个 index 空间**。
 *
 * 事故记录：文本标记用「未过滤的 DOM 序号」，事实采集用「过滤掉不可见元素后的下标」。
 * 页面里只要存在一个不可见节点（本例是一个 <br>），它之后所有文本元素的字体就会被
 * 写到隔壁元素上 —— 18 个文本元素里错了 15 个，而且没有任何断言能发现：page-facts
 * 看起来「字体已测量」，只是测到了别人头上。所以判定逻辑上提到这里，两个关卡拼同一段。
 *
 * 另：判定「元素是否自己排版了文本」必须看直接子文本节点。innerText 会把后代文本
 * 一起算进来，于是每个祖先容器都成了「有 291 个字符、21 段 rect」的伪文本元素，
 * 它的 rect 并集只是子元素矩形的凑合，不是任何一次真实排版的结果。 */
const SHARED_PRELUDE = `
  const visible = e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.display !== 'none'
      && s.visibility !== 'hidden' && Number(s.opacity) > 0;
  };
  const ownTextOf = e => Array.from(e.childNodes)
    .filter(n => n.nodeType === Node.TEXT_NODE)
    .map(n => n.nodeValue || '')
    .join(' ')
    .replace(/\\s+/g, ' ')
    .trim();
`;

/* 给「自己承载文本」的元素打标记，供 CDP 按 index 取实际命中字体。必须与
 * COLLECT_FACTS 用同一个 index 空间（同一套 visible 过滤 + 同一套下标编号）。 */
const MARK_TEXT = `() => {${SHARED_PRELUDE}
  const marked = [];
  Array.from(document.querySelectorAll('body *')).filter(visible).forEach((e, index) => {
    if (ownTextOf(e) && e.tagName !== 'IMG') {
      e.setAttribute('data-iherefor-text', String(index));
      marked.push(index);
    }
  });
  return {
    marked,
    // 一并记下两个计数：它们的差额就是「DOM 序号 vs 过滤后下标」错位的空间。
    // 差额为 0 时本页测不出错位，回归用例可据此断言 fixture 仍在真实地制造这个条件。
    domNodeCount: document.querySelectorAll('body *').length,
    visibleNodeCount: Array.from(document.querySelectorAll('body *')).filter(visible).length,
  };
}`;

/* 在页面里跑的采集逻辑。字符串形式传入，避免闭包捕获外部变量造成「脚本注入」
 * 之类的误判，也让这段逻辑可以被单独 review。 */
const COLLECT_FACTS = `(scroll) => {${SHARED_PRELUDE}
  const round = (v) => Math.round(v * 1000) / 1000;
  /* 位置基准必须是**直接父视图**，所以每个元素都要带上「它的父是谁」。
   *
   * 两处容易做错：
   * 1) index 是**过滤后**的下标空间（visible 之后重排），父下标必须在**同一空间**里取。
   *    直接拿 DOM 序号或 parentElement 本身，会得到与 elements 数组对不上的编号 ——
   *    而错位的编号看起来只是个普通整数，不会报错。
   * 2) 向上找的是最近的**可见**祖先，允许跳过不可见中间层。这与实现侧一致：
   *    不可见的中间层不会生成视图，拿它当锚点在原生里根本不存在。
   *    parentHops 如实记下跳过了几层，层级被折叠过的地方不能假装是相邻父子。
   * parentIndex === null 的含义是「直接父视图就是整屏画布」（body/root），
   * 这正是实现计划里 \`of: "root"\` 的适用场景 —— 它应当是少数，不是默认。
   */
  const visibleEls = Array.from(document.querySelectorAll('body *')).filter(visible);
  const visibleIndex = new Map(visibleEls.map((e, i) => [e, i]));
  const nearestVisibleAncestor = (e) => {
    let hops = 0, p = e.parentElement;
    while (p && p !== document.body && p !== document.documentElement) {
      const found = visibleIndex.get(p);
      if (found !== undefined) return { index: found, hops };
      hops += 1;
      p = p.parentElement;
    }
    return { index: null, hops };
  };
  /* 绝对定位元素还有第二个基准：**最近的建立了坐标系的可见祖先**。
   * CSS 里 absolute 的坐标原点是最新的 position !== static 的祖先，不是 DOM 父；
   * 而原生实现里子视图一律相对直接父视图的 bounds 定位，没有「定位祖先」这个概念。
   * 两者必须分开记，否则遇到「中间夹一层 static 的孙元素被 absolute」就会算错原点：
   * 实测这页面上 3 个 absolute 元素的定位祖先恰好都等于可见祖先（Lanhu 导出的容器
   * 大多自带 position: relative），但那是这一页的巧合，不能当假设。
   * 不可见的 positioned 祖先要跳过继续找 —— 实现侧不会为不可见层建视图，锚不到它。 */
  const nearestPositionedVisibleAncestor = (e) => {
    let p = e.parentElement;
    while (p && p !== document.body && p !== document.documentElement) {
      if (getComputedStyle(p).position !== 'static') {
        const found = visibleIndex.get(p);
        if (found !== undefined) return found;
      }
      p = p.parentElement;
    }
    return null;
  };
  return visibleEls.map((e, index) => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    const text = (e.innerText || '').trim();
    const ancestor = nearestVisibleAncestor(e);
    const facts = {
      index, tag: e.tagName.toLowerCase(), id: e.id || null,
      className: typeof e.className === 'string' ? e.className : null,
      // 父视图：最近可见祖先在 elements 里的下标；null = 直接父视图即整屏画布。
      parentIndex: ancestor.index,
      // 到那个可见祖先之间跳过的不可见层数（0 = 直接相邻）。>0 表示层级被折叠过。
      parentHops: ancestor.hops,
      // text 是 innerText 聚合值（含后代文本），保留它是为了让「祖先容器」可被识别：
      // 只有当祖先的聚合文本包含后代的文本时，才能把祖先判成容器而非真实文本元素。
      // 判断「这个元素是否自己排版了文本」一律用下面的 ownText / ownsText，别用 text。
      text: text.slice(0, 300),
      rect: { x: r.x, y: r.y, width: r.width, height: r.height },
      // rectInReference：元素在 reference.png 里的像素 rect。截图不滚动，所以
      // 文档坐标 = 视口坐标 + scroll；再乘 dpr 得到图片像素。
      rectInReference: {
        x: round((r.x + scroll.x) * scroll.dpr),
        y: round((r.y + scroll.y) * scroll.dpr),
        width: round(r.width * scroll.dpr),
        height: round(r.height * scroll.dpr),
      },
      style: { display:s.display, position:s.position, zIndex:s.zIndex, overflow:s.overflow,
        color:s.color, backgroundColor:s.backgroundColor, backgroundImage:s.backgroundImage,
        fontFamily:s.fontFamily, fontSize:s.fontSize, fontWeight:s.fontWeight,
        fontStyle:s.fontStyle, lineHeight:s.lineHeight, letterSpacing:s.letterSpacing,
        borderRadius:s.borderRadius, boxShadow:s.boxShadow, opacity:s.opacity,
        transform:s.transform, objectFit:s.objectFit, backgroundSize:s.backgroundSize },
      role: e.getAttribute('role'), ariaLabel: e.getAttribute('aria-label'),
      src: e.tagName === 'IMG' ? (e.currentSrc || e.src) : null,
    };
    // 绝对定位元素才有第二个基准（见上面的 nearestPositionedVisibleAncestor）：
    //   number = 最近「可见且建立了坐标系」的祖先下标（可能不等于 parentIndex）
    //   null   = 没有这样的祖先，坐标原点就是视口 / 画布
    // 非 absolute/fixed 元素不写这个字段：缺字段表示「不适用」，与 null（基准是视口）不同。
    if (s.position === 'absolute' || s.position === 'fixed') {
      facts.positioningContextIndex = nearestPositionedVisibleAncestor(e);
    }
    // 文本度量：用 Range 量**真实排版结果**，这是判断字体替换是否成立的唯一依据。
    // 不信任 document.fonts.check()——它对不存在的字体族也返回 true（见 browser-meta
    // 的 fontProbeNote），所以「CSS 声明了什么」不能当作「渲染用了什么」。
    const ownText = ownTextOf(e);
    facts.ownText = ownText.slice(0, 300);
    facts.ownsText = ownText.length > 0;
    // 记录本元素被 CDP 查询时使用的 index。main() 会断言它与 index 相等：一旦不等，
    // 说明标记与采集的 index 空间又漂移了，本次的 primaryFont 归属不可信。
    facts.textMark = e.getAttribute('data-iherefor-text');
    if (ownText && e.tagName !== 'IMG') {
      /* 只量**本元素直接承载的文本**的排版矩形。
       * selectNodeContents(e) 会把后代文本一起圈进来，于是一个「自己带一个词、又包着
       * 一段子文本」的元素会得到一个横跨各行的并集框 —— 契约里 textMetrics.rects 的
       * 语义是「这个元素排版出来的内容在哪」，后代由后代自己的元素负责申报，不能重复。 */
      const range = document.createRange();
      const rects = [];
      let hasDescendantText = false;
      for (const node of e.childNodes) {
        if (node.nodeType !== Node.TEXT_NODE) {
          if (node.nodeType === Node.ELEMENT_NODE
              && (node.textContent || '').trim()) hasDescendantText = true;
          continue;
        }
        if (!(node.nodeValue || '').trim()) continue;
        range.selectNodeContents(node);
        for (const q of range.getClientRects()) {
          if (q.width > 0 && q.height > 0) {
            rects.push({ x: round(q.x), y: round(q.y), width: round(q.width), height: round(q.height) });
          }
        }
      }
      rects.sort((a, b) => (a.y - b.y) || (a.x - b.x));
      const lines = new Map();
      for (const q of rects) {
        const key = Math.round(q.y * 2) / 2;   // 行高通常整数或带 .5，按 0.5 归并
        const prev = lines.get(key);
        if (prev) { prev.width = Math.max(prev.width, q.width); prev.runs += 1; }
        else lines.set(key, { y: q.y, height: q.height, width: q.width, runs: 1 });
      }
      facts.textMetrics = {
        charCount: ownText.length,
        lineCount: lines.size,
        // ownOnlyText：rects 只覆盖本元素直接文本（已排除后代文本）。
        ownOnlyText: true,
        // hasDescendantTextElement：本元素既自己排版文本、又包着别的文本元素。
        // 这类元素容易被当成祖先容器，审计脚本可据此降权。
        hasDescendantTextElement: hasDescendantText,
        // advanceWidth：最长一行的排版宽度（CSS px）。字体被替换时这里会变。
        advanceWidth: round(rects.reduce((m, q) => Math.max(m, q.width), 0)),
        totalInlineWidth: round(rects.reduce((m, q) => m + q.width, 0)),
        rects,
      };
    }
    return facts;
  });
}`;

/* 用 CDP 取「真正命中的平台字体」。这是 Chromium 唯一可靠的答案：
 * CSS.getPlatformFontsForNode 返回 familyName/postScriptName/glyphCount，
 * glyphCount 还能说明该字体承担了多少字形（混合字体时会有多条）。 */
async function platformFontsFor(context, page) {
  const cdp = await context.newCDPSession(page);
  await cdp.send('DOM.enable');
  await cdp.send('CSS.enable');
  const { root } = await cdp.send('DOM.getDocument', { depth: -1 });
  // 只对有文本的元素取字体：容器级元素返回空数组，全量请求纯属浪费往返。
  const { nodeIds } = await cdp.send('DOM.querySelectorAll', {
    nodeId: root.nodeId, selector: '[data-iherefor-text]',
  });
  const byIndex = {};
  for (const nodeId of nodeIds) {
    const { node } = await cdp.send('DOM.describeNode', { nodeId });
    const attr = (node.attributes || []).find((v, i, all) => all[i - 1] === 'data-iherefor-text');
    if (!attr) continue;
    const result = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    byIndex[attr] = (result.fonts || []).map(f => ({
      familyName: f.familyName, postScriptName: f.postScriptName,
      isCustomFont: f.isCustomFont, glyphCount: f.glyphCount,
    }));
  }
  return byIndex;
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
  const runtimeDevice = arg('--viewport-from', null);
  const derived = runtimeDevice ? viewportFromRuntimeDevice(runtimeDevice) : null;
  const vp = derived ? derived.viewport : viewport(arg('--viewport', '393x852'));
  const scale = derived ? derived.scale : Number(arg('--scale', '2'));
  /* 与设备截图比对时只能截视口：整页截图（document 高度）与设备屏幕不是同一坐标系。 */
  const fullPage = process.argv.includes('--full-page');
  const executablePath = arg('--executable', process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined);
  const browser = await launchChromium(playwright.chromium, executablePath);
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
  /* 给有文本的元素打标记，供 CDP 按 index 取实际命中字体。标记必须在截图前打上，
   * 但 data-* 属性不参与渲染，不会改变像素。判定与编号全部来自 MARK_TEXT，与
   * COLLECT_FACTS 共用 SHARED_PRELUDE，保证两边 index 空间一致。 */
  const textMarkInfo = await page.evaluate(eval(MARK_TEXT));
  await page.screenshot({ path: path.join(output, 'reference.png'), fullPage });
  const scroll = await page.evaluate(() => ({ x: window.scrollX, y: window.scrollY, dpr: window.devicePixelRatio }));
  const elements = await page.evaluate(eval(COLLECT_FACTS), scroll);
  const elementsByIndex = new Map(elements.map(e => [e.index, e]));

  let fontsByIndex = {}, fontMeasurement = {
    method: 'cdp:CSS.getPlatformFontsForNode', ok: true,
    // glyphCount 是**该节点子树**渲染出的字形总数，不是「本元素自有文本」的字形数。
    // 对叶子文本元素二者相等（可用 glyphCount==charCount 校验字体有没有被归属错）；
    // 对「自己带词、又包着子文本」的元素它是子树合计，此时 primaryFont 描述的是整个
    // 子树的主字体，未必是本元素那段文字的字体。消费方据此判断该信到什么程度。
    glyphCountScope: 'subtree-of-node',
  };
  try {
    fontsByIndex = await platformFontsFor(context, page);
  } catch (error) {
    // 拿不到实际字体不能让渲染失败，但必须如实记录——否则 page-facts 会看起来「字体已测量」。
    fontMeasurement = { method: 'cdp:CSS.getPlatformFontsForNode', ok: false,
                        error: String((error && error.message) || error).slice(0, 300) };
  }
  let measuredCount = 0;
  const unjoinedIndexes = [];
  for (const [index, fonts] of Object.entries(fontsByIndex)) {
    const el = elementsByIndex.get(Number(index));
    if (!el) { unjoinedIndexes.push(Number(index)); continue; }
    el.fontsResolved = fonts || [];
    el.primaryFont = fonts && fonts.length ? fonts.slice().sort((a, b) => b.glyphCount - a.glyphCount)[0] : null;
    measuredCount += 1;
  }

  /* 自查：标记时写进 DOM 的 index 必须等于采集时给该元素编的下标。二者不等就说明
   * 两个关卡的 index 空间又漂移了，此时 fontsResolved/primaryFont 是隔壁元素的数据，
   * 必须显式报出来 —— 这正是「字体已测量但测错了人」那次事故的形态。 */
  const textOwners = elements.filter(e => e.ownsText);
  const textMarkMismatches = textOwners
    .filter(e => e.textMark !== String(e.index))
    .map(e => ({ index: e.index, textMark: e.textMark, own: (e.ownText || '').slice(0, 24) }));
  const fontJoin = {
    markedElements: textMarkInfo.marked.length,
    joinedElements: measuredCount,
    unjoinedIndexes,
    textElements: textOwners.length,
    textMarkMatches: textOwners.length - textMarkMismatches.length,
    textMarkMismatchCount: textMarkMismatches.length,
    textMarkMismatches: textMarkMismatches.slice(0, 10),
    domNodeCount: textMarkInfo.domNodeCount,
    visibleNodeCount: textMarkInfo.visibleNodeCount,
    // 「DOM 序号 − 过滤后下标」的错位空间。> 0 表示本页确实存在被过滤掉的节点，
    // 也就意味着两个关卡若用不同编号方式必然错位 —— 这是自检要覆盖的条件。
    indexSpaceSkew: textMarkInfo.domNodeCount - textMarkInfo.visibleNodeCount,
    ok: textMarkMismatches.length === 0 && unjoinedIndexes.length === 0,
  };

  /* document.fonts.check() 对任意未安装的字体族也返回 true，因此它**不能**用来
   * 判断字体是否可用。保留一次探测结果并明确标注它的语义，防止后人再踩。 */
  const fontProbe = await page.evaluate(() => ({
    probeNote: 'document.fonts.check() 对不存在的字体族同样返回 true，不能用于判断 fallback',
    declaredFamilies: Array.from(new Set(Array.from(document.querySelectorAll('body *'))
      .map(e => getComputedStyle(e).fontFamily))).slice(0, 50),
    fontFaceRules: Array.from(document.fonts || []).map(f => ({ family: f.family, status: f.status, weight: f.weight, style: f.style })),
  }));

  const referenceImagePath = path.join(output, 'reference.png');
  let referenceImage;
  try {
    referenceImage = { path: 'reference.png', ...alphaBounds(referenceImagePath) };
  } catch (error) {
    referenceImage = { path: 'reference.png', error: String((error && error.message) || error).slice(0, 300) };
  }

  /* 逐个图片资源测 alpha 内容 bounds。SKILL.md 要求「图片 frame 已缩放」不等于
   * 「图片已缩放」：资源带透明留白时，只有 alpha bounds 能证明内容绘制区域对不对。
   * 这里把源资源的 alpha bounds 与自然尺寸记进事实表，审计脚本再拿它跟映射后的
   * frame 比。只处理本地文件，data: URI 与远程 URL 记为 not-measured。 */
  const assetCache = new Map();
  const assetOf = (rawUrl, role) => {
    if (!rawUrl) return null;
    const url = String(rawUrl);
    if (url.startsWith('data:')) return { role, url: url.slice(0, 64) + '…', measured: false, reason: 'data-uri' };
    if (!url.startsWith('file://')) return { role, url, measured: false, reason: 'non-local-url' };
    const filePath = decodeURIComponent(url.replace(/^file:\/\//, ''));
    if (assetCache.has(filePath)) return { role, url, path: filePath, ...assetCache.get(filePath) };
    let entry;
    try {
      const bounds = alphaBounds(filePath);
      const stat = fs.statSync(filePath);
      entry = { measured: true, bytes: stat.size, ...bounds };
    } catch (error) {
      entry = { measured: false, reason: String((error && error.message) || error).slice(0, 200) };
    }
    assetCache.set(filePath, entry);
    return { role, url, path: filePath, ...entry };
  };

  const backgroundUrls = await page.evaluate(() => Array.from(document.querySelectorAll('body *')).map((e, index) => {
    const bi = getComputedStyle(e).backgroundImage || '';
    const urls = Array.from(bi.matchAll(/url\((?:"|')?([^"')]+)(?:"|')?\)/g)).map(m => m[1]);
    return { index, urls };
  }));
  const backgroundByIndex = new Map(backgroundUrls.map(b => [b.index, b.urls]));
  for (const el of elements) {
    const assets = [];
    const img = assetOf(el.src, 'img');
    if (img) assets.push(img);
    for (const url of (backgroundByIndex.get(el.index) || []).slice(0, 4)) {
      const asset = assetOf(url, 'background');
      if (asset) assets.push(asset);
    }
    if (assets.length) {
      el.assets = assets;
      // 只要有一张图藏着透明留白，就必须在审计里被看见：这是「frame 对了但图没对」的根因。
      el.assetsWithPadding = assets.filter(a => a.measured && a.bounds &&
        (a.bounds.width < a.width || a.bounds.height < a.height)).length;
    }
  }

  const facts = {
    schemaVersion: 3,
    title: await page.title(), url: page.url(),
    viewport: { width: vp.width, height: vp.height, devicePixelRatio: scale,
                scrollX: scroll.x, scrollY: scroll.y },
    documentSize: await page.evaluate(() => ({ width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight })),
    coordinateSpace: {
      note: 'rect 是 CSS px（视口相对）；rectInReference 是 reference.png 的像素坐标 = (rect + scroll) * devicePixelRatio',
      rectInReferenceFormula: '(rect + viewport.scroll) * viewport.devicePixelRatio',
      parentNote: 'parentIndex 是最近可见祖先在 elements 里的下标（同一套 visible 过滤 + 同一套下标编号）；'
                + 'null 表示直接父视图就是整屏画布，即实现计划里 of:"root" 的适用场景。'
                + 'parentHops 是到该祖先之间跳过的不可见层数，>0 说明层级被折叠过。'
                + 'positioningContextIndex 只出现在 absolute/fixed 元素上：它是最近「可见且 position!==static」'
                + '的祖先下标（CSS 下坐标原点所在），可能不等于 parentIndex；null 表示原点即视口。'
                + '缺该字段表示该元素不是绝对定位，「不适用」与 null 语义不同。'
                + 'schemaVersion 3 起才有这些字段；读不到时不得假设层级已知。',
    },
    referenceImage,
    textMetricsNote: 'textMetrics.advanceWidth 是排版宽度（CSS px），字体被替换时必然变化；用它判断 fallback，不要用 CSS 声明的 fontFamily',
    elements,
  };
  const meta = { schemaVersion: 3, entry, viewport: vp, scale, viewportSource: derived ? `runtime-device:${path.resolve(runtimeDevice)}` : 'cli', fullPage, screenshotPixels: { width: vp.width * scale, height: vp.height * scale }, browser: await browser.version(), capturedAt: new Date().toISOString(), styleInjection, console: consoleMessages, failedRequests, fontMeasurement, fontMeasurementCoverage: { textElements: textMarkInfo.marked.length, measured: measuredCount }, fontJoin, fontProbe, images: await page.evaluate(() => Array.from(document.images).map(i => ({ src:i.currentSrc || i.src, complete:i.complete, naturalWidth:i.naturalWidth, naturalHeight:i.naturalHeight }))) };
  fs.writeFileSync(path.join(output, 'page-facts.json'), JSON.stringify(facts, null, 2));
  fs.writeFileSync(path.join(output, 'browser-meta.json'), JSON.stringify(meta, null, 2));
  await browser.close();
  console.log(JSON.stringify({ output, screenshot: referenceImagePath, facts: path.join(output, 'page-facts.json'), meta: path.join(output, 'browser-meta.json'), textFontsMeasured: measuredCount, referenceImage, assetsMeasured: assetCache.size }, null, 2));
}
main().catch(e => { console.error(`render_reference: ${e.message}`); process.exit(1); });
