#!/usr/bin/env bash
# skill 脚本级回归测试（不依赖 LLM）。
# 用法：bash scripts/tests/run_all.sh
# 退出码：0 = 全部通过；1 = 存在失败。
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2

PY=".runtime/venv/bin/python3"
if [ ! -x "$PY" ]; then
  echo "警告：未找到 .runtime/venv，回退到系统 python3（可能缺少 Pillow）" >&2
  PY="$(command -v python3)"
fi

# 未下载 Playwright 自带的 Chromium 时，复用本机 Chrome（文档支持的兜底路径）。
if [ -z "${PLAYWRIGHT_EXECUTABLE_PATH:-}" ]; then
  downloaded=0
  for dir in "$HOME"/Library/Caches/ms-playwright/chromium-*; do
    [ -d "$dir" ] && downloaded=1
  done
  chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  if [ "$downloaded" -eq 0 ] && [ -x "$chrome" ]; then
    export PLAYWRIGHT_EXECUTABLE_PATH="$chrome"
    echo "提示：未检测到 Playwright Chromium，回退到本机 Chrome" >&2
  fi
fi

failed=0
run() {
  local label="$1"; shift
  printf '\n== %s ==\n' "$label"
  if "$@"; then
    printf 'PASS  %s\n' "$label"
  else
    printf 'FAIL  %s\n' "$label"
    failed=1
  fi
}

run "compare_reference 比例阈值与尺寸校验" "$PY" scripts/tests/test_compare_reference.py
run "render_reference 动画禁用注入生效"   "$PY" scripts/tests/test_render_injection.py
run "render_reference 基准与设备同源"     "$PY" scripts/tests/test_reference_same_source.py
if command -v node >/dev/null 2>&1; then
  run "browser-launch 启动回退策略"        node scripts/tests/test_browser_launch.mjs
else
  echo "跳过 browser-launch 用例：未找到 node" >&2
fi
run "check_lanhu_mcp 注册入口一致性"       "$PY" scripts/tests/test_check_lanhu_mcp.py
run "discover_xcode_environment 设备探测"  "$PY" scripts/tests/test_discover_xcode.py
run "validate_run 产物契约校验"           "$PY" scripts/tests/test_validate_run.py
run "init_ui_workspace 目录与索引"        "$PY" scripts/tests/test_init_ui_workspace.py
run "文档与脚本参数漂移"                  "$PY" scripts/tests/test_doc_commands.py
# 评测判分器自检：零凭据、零 LLM，保证每个用例的判分器都有「必须过／必须挂」两份样本。
run "评测判分器自检（无需引擎凭据）"       "$PY" evals/harness/selfcheck.py

printf '\n----------------------------------------\n'
if [ "$failed" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME FAILED"
fi
exit "$failed"
