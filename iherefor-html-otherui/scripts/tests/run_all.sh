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

run "layout_proportions 比例规格与禁止字面量" "$PY" scripts/tests/test_layout_proportions.py
run "typeFacts 样式恒量事实溯源"         "$PY" scripts/tests/test_type_facts.py
run "check_adaptive_layout 宽度轴静态核对"  "$PY" scripts/tests/test_check_adaptive_layout.py
run "audit_adaptive 多宽度几何审计"       "$PY" scripts/tests/test_audit_adaptive.py
run "diff_device_variants 双稿尺寸 diff"  "$PY" scripts/tests/test_diff_device_variants.py
run "check_pbxproj_ids pbxproj Object ID 唯一性" "$PY" scripts/tests/test_check_pbxproj_ids.py
run "check_lanhu_mcp 注册入口一致性"       "$PY" scripts/tests/test_check_lanhu_mcp.py
run "lanhu_design_facts 设计事实解析还原"   "$PY" scripts/tests/test_lanhu_design_facts.py
run "discover_xcode_environment 设备探测"  "$PY" scripts/tests/test_discover_xcode.py
run "validate_run 产物契约校验"           "$PY" scripts/tests/test_validate_run.py
run "init_ui_workspace 目录与索引"        "$PY" scripts/tests/test_init_ui_workspace.py
run "decide_next_step 停止判定"           "$PY" scripts/tests/test_decide_next_step.py
run "文档与脚本参数漂移"                  "$PY" scripts/tests/test_doc_commands.py
# 变异探针会临时改写被测源码，因此**不进本套件**（跑法见 evals/README.md）；
# 它证明的是「上面这些断言不是空的」，改完校验器后应手动跑一次。
# 评测判分器自检：零凭据、零 LLM，保证每个用例的判分器都有「必须过／必须挂」两份样本。
run "评测判分器自检（无需引擎凭据）"       "$PY" evals/harness/selfcheck.py

printf '\n----------------------------------------\n'
if [ "$failed" -eq 0 ]; then
  echo "ALL PASS"
else
  echo "SOME FAILED"
fi
exit "$failed"
