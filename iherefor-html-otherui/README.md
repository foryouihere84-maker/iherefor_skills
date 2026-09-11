# iherefor-html-otherui

把 Lanhu（蓝湖）导出的**可运行 HTML/CSS/JS 页面**作为视觉基准，由 Agent 生成并验证 iOS / Android
原生 UI 的 Agent Skill。

输入是完整页面（HTML + CSS + JS + 资源），不是仅靠结构化图层 JSON；输出是目标技术栈的生产代码，
并且必须经过「编译 → 运行截图 → 与基准像素比对 → 修复」的闭环才算完成。

## 支持的目标模式

| 模式 | 语言 | UI 技术 |
|---|---|---|
| `ios-swiftui` | Swift | SwiftUI |
| `ios-uikit-swift` | Swift | UIKit |
| `ios-uikit-objective-c` | Objective-C | UIKit |
| `android-compose-kotlin` | Kotlin | Jetpack Compose |
| `android-views-kotlin` | Kotlin | Android Views/XML |
| `android-views-java` | Java | Android Views/XML |

每次任务必须显式选择目标模式；不同模式使用不同的 run，不能互相借用通过证据。

## 目录结构

```text
.
├── SKILL.md                  # 主入口：核心原则与强制 Agent loop
├── references/               # 按需加载的细节契约（10 篇）
├── scripts/                  # 确定性工具：渲染、测量、比帧、编译探测、契约校验
│   └── tests/                # 脚本级回归测试（不依赖 LLM）
├── agents/openai.yaml        # 界面元数据
├── index.html                # 本地 diff 查看器（人工验收入口）
├── lanhu-mcp-server/         # Lanhu MCP 输入层实现
└── testUIProject/            # 回归样例工程（非交付物）
```

## 安装运行时依赖

```bash
# Python（compare_reference.py / validate_run.py 等）
python3 -m venv .runtime/venv
.runtime/venv/bin/pip install -r requirements.txt

# Node（render_reference.mjs / inspect_page.mjs）
npm install
npx playwright install chromium        # 或设置 PLAYWRIGHT_EXECUTABLE_PATH 复用本机 Chrome
```

Lanhu 输入层还需要构建并注册 MCP，见 [`lanhu-mcp-server/README.md`](lanhu-mcp-server/README.md)。

## 自检

```bash
bash scripts/tests/run_all.sh                                   # 7 个脚本级回归用例
.runtime/venv/bin/python3 scripts/validate_run.py --run <run-dir>   # 单次 run 的产物契约校验
```

## 工作流一览

1. 探测运行时设备尺寸 → 2. 以同源参数渲染基准图 → 3. 建立页面事实表 → 4. 输出实现计划 →
5. Agent 编写生产代码 → 6. 编译 / 运行 / 截图 → 7. 像素比对与修复迭代 → 8. 交付闸门。

产物统一落在 `.ihereforUI/`，结构以 [`references/artifact-contract.md`](references/artifact-contract.md)
为唯一事实来源。所有强制约束见 [`SKILL.md`](SKILL.md)。
