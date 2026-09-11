/* Chromium 启动策略：兼容两种浏览器布局。
 *
 * Playwright 1.49+ 把 headless 的默认实现拆成单独分发的 chromium-headless-shell。
 * 只装了完整 Chromium 构建（或第二份下载被中断）时，默认 launch 会直接抛
 * 「Executable doesn't exist」——看起来像脚本坏了，其实只是少一份浏览器。
 * 因此这里显式指定 executablePath 优先，否则先试完整 Chromium 通道，
 * 只有该通道确实缺失时才退回 Playwright 的默认布局。
 */
const MISSING_BROWSER = /Executable doesn't exist|is not installed|Please run the following command/i;

export async function launchChromium(chromium, executablePath) {
  if (executablePath) {
    return chromium.launch({ headless: true, executablePath });
  }
  try {
    return await chromium.launch({ headless: true, channel: 'chromium' });
  } catch (error) {
    const message = String((error && error.message) || error);
    if (!MISSING_BROWSER.test(message)) throw error;
    return chromium.launch({ headless: true });
  }
}
