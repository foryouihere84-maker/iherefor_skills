#!/usr/bin/env node
/* browser-launch 的启动回退策略测试：不启动真实浏览器，用桩验证分支选择。 */
import { launchChromium } from '../browser-launch.mjs';

let failures = 0;
function check(name, condition, detail = '') {
  if (condition) {
    console.log(`  ok   ${name}`);
  } else {
    console.log(`  FAIL ${name} ${detail}`);
    failures += 1;
  }
}

/* 记录每次 launch 的入参，并按调用序号决定行为。 */
function stub(behaviour) {
  const calls = [];
  return {
    calls,
    launch: async (options) => {
      calls.push(options);
      return behaviour(options, calls.length);
    },
  };
}

// 1. 显式 executablePath 优先，且不再指定 channel（Chrome 兜底路径）。
{
  const chromium = stub(() => ({ id: 'pinned' }));
  const browser = await launchChromium(chromium, '/tmp/chrome');
  check('executablePath 优先', browser.id === 'pinned' && chromium.calls.length === 1);
  check('executablePath 场景不带 channel',
    chromium.calls[0].executablePath === '/tmp/chrome' && !('channel' in chromium.calls[0]));
}

// 2. 完整 Chromium 可用时一次命中，不产生第二次启动。
{
  const chromium = stub(() => ({ id: 'channel' }));
  const browser = await launchChromium(chromium, undefined);
  check('默认走 chromium 通道',
    browser.id === 'channel' && chromium.calls[0].channel === 'chromium' && chromium.calls.length === 1);
}

// 3. 只装了 chromium-headless-shell、没有完整构建时退回默认布局。
{
  const chromium = stub((options, n) => {
    if (n === 1) throw new Error("browserType.launch: Executable doesn't exist at /x/chrome-headless-shell");
    return { id: 'fallback' };
  });
  const browser = await launchChromium(chromium, undefined);
  check('通道缺失时退回默认布局',
    browser.id === 'fallback' && chromium.calls.length === 2 && !('channel' in chromium.calls[1]));
}

// 4. 与浏览器缺失无关的启动错误必须原样抛出，不能被吞成「换个布局再试」。
{
  const chromium = stub(() => { throw new Error('Target page, context or browser has been closed'); });
  let thrown = null;
  try {
    await launchChromium(chromium, undefined);
  } catch (error) {
    thrown = error;
  }
  check('无关错误原样抛出', thrown !== null && chromium.calls.length === 1);
}

if (failures > 0) {
  console.error(`browser-launch: ${failures} 项失败`);
  process.exit(1);
}
console.log('browser-launch: 全部通过');
