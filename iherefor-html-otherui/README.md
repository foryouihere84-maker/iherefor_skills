# iherefor-html-otherui

把 Lanhu（蓝湖）设计稿映射为 iOS / Android 原生 UI 的 Agent Skill。

**输入是双链路**（详见 `references/lanhu-input.md`）：
- **主链路（默认）**：`lanhu-mcp` 的 `lanhu_get_design_overview` 给出 `nodes[].bounds` 绝对坐标（组件几何权威），
  据此直接生成布局契约与原生代码；
- **备用链路（fallback）**：`bounds` 拿不到或不可信时，回退到「渲染 HTML → 读 DOM `page-facts.json`」的旧路径。

样式恒量（字号/颜色/圆角/描边）以 `inspect_design_region` 的 `raw_style` 为准、切图以 `export_design_assets`
为准；输出是目标技术栈的生产代码，
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

```
.
├── SKILL.md                  # 主入口：核心原则与强制 Agent loop
├── references/               # 按需加载的细节契约
├── scripts/                  # 确定性工具：布局契约、编译探测、契约校验
│   └── tests/                # 脚本级回归测试（不依赖 LLM）
├── agents/openai.yaml        # 界面元数据
├── lanhu-mcp/                # Lanhu MCP 输入层（dsphper/lanhu-mcp，Python 版）
├── evals/                    # skill-up 评测套件
└── testUIProject/            # 回归样例工程（非交付物）
```

## 安装运行时依赖

```bash
# Python（校验脚本 validate_run.py / check_layout_proportions.py 等）
python3 -m venv .runtime/venv
.runtime/venv/bin/pip install -r requirements.txt
```

Lanhu 输入层使用社区维护的 `dsphper/lanhu-mcp`（Python 版，源码随本 skill 分发在 `lanhu-mcp/`），
需配置 `.env` 凭据并注册为 MCP stdio server，见 [`references/lanhu-input.md`](references/lanhu-input.md)。

## 自检

```bash
bash scripts/tests/run_all.sh                                   # 脚本级回归用例
.runtime/venv/bin/python3 scripts/validate_run.py --run <run-dir>   # 单次 run 的产物契约校验
```

## 工作流一览

1. 取 `bounds` 几何事实（主链路，拿不到才渲染 DOM 兜底）→ 2. 探测运行时设备尺寸 →
3. 建立页面事实表 → 4. 输出实现计划 → 5. Agent 编写生产代码 → 6. 编译通过 → 7. 交付闸门。

产物统一落在 `.ihereforUI/`，结构以 [`references/artifact-contract.md`](references/artifact-contract.md)
为唯一事实来源。所有强制约束见 [`SKILL.md`](SKILL.md)。
