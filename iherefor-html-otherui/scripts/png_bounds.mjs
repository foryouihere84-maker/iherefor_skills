/* 纯 JS 的 PNG 解码：只为拿到 alpha 内容 bounds，不引入任何依赖。
 *
 * 为什么不用 canvas：file:// 页面里的 <img> 会污染 canvas，getImageData 直接抛
 * SecurityError（除非给浏览器加 --allow-file-access-from-files，那会改变渲染环境，
 * 让基准图不再是「默认配置下的结果」）。而 Playwright 输出的 PNG 一定是 8bit、
 * 非隔行、filter 0–4，node 自带 zlib 就够解。
 *
 * alpha bounds 是「图片有没有透明留白」的唯一可观测量：SKILL.md 要求验证图片
 * 可见 bounds 与 Lanhu 可见 bounds 成比例，但只检查 frame 是查不出留白的。
 */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const zlib = require('zlib');
const fs = require('fs');

const CHANNELS = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 };

/* 逐行反滤波。filter 类型见 PNG 规范 9.2：0 None / 1 Sub / 2 Up / 3 Average / 4 Paeth。 */
function unfilter(raw, width, height, channels) {
  const stride = width * channels;
  const out = Buffer.alloc(height * stride);
  const zero = Buffer.alloc(stride);
  let offset = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = raw[offset];
    offset += 1;
    const line = raw.subarray(offset, offset + stride);
    offset += stride;
    if (line.length < stride) throw new Error(`IDAT 数据不足：第 ${y} 行只有 ${line.length}/${stride} 字节`);
    const prev = y ? out.subarray((y - 1) * stride, y * stride) : zero;
    const cur = out.subarray(y * stride, (y + 1) * stride);
    for (let i = 0; i < stride; i += 1) {
      const a = i >= channels ? cur[i - channels] : 0;
      const b = prev[i];
      const c = i >= channels ? prev[i - channels] : 0;
      let value = line[i];
      if (filter === 1) value += a;
      else if (filter === 2) value += b;
      else if (filter === 3) value += (a + b) >> 1;
      else if (filter === 4) {
        const pa = Math.abs(b - c);
        const pb = Math.abs(a - c);
        const pc = Math.abs(a + b - 2 * c);
        value += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
      } else if (filter !== 0) {
        throw new Error(`不支持的 PNG 行滤波类型：${filter}`);
      }
      cur[i] = value & 0xff;
    }
  }
  return out;
}

export function readPng(path) {
  const buf = fs.readFileSync(path);
  if (buf.length < 8 || buf.readUInt32BE(0) !== 0x89504e47) {
    throw new Error(`不是 PNG 文件：${path}`);
  }
  let offset = 8;
  let width = 0, height = 0, depth = 0, colorType = 0, interlace = 0;
  const idat = [];
  while (offset + 8 <= buf.length) {
    const length = buf.readUInt32BE(offset);
    const type = buf.toString('ascii', offset + 4, offset + 8);
    const data = buf.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      depth = data[8];
      colorType = data[9];
      interlace = data[12];
    } else if (type === 'IDAT') {
      idat.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  if (depth !== 8 || interlace !== 0) {
    throw new Error(`只支持 8bit 非隔行 PNG：depth=${depth} interlace=${interlace}`);
  }
  const channels = CHANNELS[colorType];
  if (!channels) throw new Error(`不支持的 PNG colorType：${colorType}`);
  return { width, height, channels, colorType, pixels: unfilter(zlib.inflateSync(Buffer.concat(idat)), width, height, channels) };
}

/* 非透明内容的包围盒。threshold=0 表示「只要有任何不透明像素就算内容」；
 * fullyOpaque 说明这张图没有透明通道或全图不透明，此时 bounds 必等于整图，
 * 不能据此推断「没有留白」——要看 opaqueRatio。 */
export function alphaBounds(path, threshold = 0) {
  const png = readPng(path);
  const { width, height, channels, colorType, pixels } = png;
  const alphaIndex = colorType === 6 ? 3 : (colorType === 4 ? 1 : null);
  if (alphaIndex === null) {
    return { width, height, fullyOpaque: true, opaqueRatio: 1, bounds: { x: 0, y: 0, width, height } };
  }
  const stride = width * channels;
  let minX = width, minY = height, maxX = -1, maxY = -1, opaque = 0;
  for (let y = 0; y < height; y += 1) {
    const row = y * stride;
    for (let x = 0; x < width; x += 1) {
      if (pixels[row + x * channels + alphaIndex] > threshold) {
        opaque += 1;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  const total = width * height;
  if (maxX < 0) {
    return { width, height, fullyOpaque: false, opaqueRatio: 0, bounds: null,
             note: '整图全透明，没有任何可见内容' };
  }
  return {
    width, height, fullyOpaque: false,
    opaqueRatio: Number((opaque / total).toFixed(6)),
    bounds: { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 },
  };
}
