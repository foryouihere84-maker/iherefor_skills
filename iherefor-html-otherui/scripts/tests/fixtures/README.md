# 回归测试 fixture

这些文件是**真实事故的现场证据**，不是构造数据。任何修改都必须保留其原始数值特征，否则测试就失去了意义。

## 来源

取自 `testUIProject/.ihereforUI/pages/plan-selection/runs/20260907-150000-objc-011/`（iPhone 17 模拟器，`ios-uikit-objective-c`）。

| 文件 | 原始路径 | 说明 |
|---|---|---|
| `diff-full-page.json` | `diff/full-page.json` | 当时的比较器输出 |
| `reference.png` | `reference/reference.png` | HTML 基准截图，786×1704 |
| `actual-device.png` | `actual/ios-objective-c.png` | 目标 App 真机/模拟器截图，1206×2622 |
| `runtime-device.json` | `runs/20260907-104500-objc-runtime/runtime-device.json` | 运行时设备尺寸证据（402×874 @3） |

## 为什么它重要

这份输出同时记录了两个问题：

- `changedRatio = 0.375`，但 `status = "pass"` —— 比较器没有比例阈值判定，**37.5% 像素差异被判定为通过**。
- 基准图 786×1704（393×852 @2）与设备截图 1206×2622（402×874 @3）**不同源**；当时的对比用的是降采样派生图 `actual/ios-objective-c-reference-size.png`，绕过了唯一那道尺寸校验。

因此 `test_compare_reference.py` 用 `reference.png` + `actual-device.png` 作为输入时，**期望结果是 `fail`**。修复前该测试必须为红。

## 环境基线（S0.3 记录）

```text
node        v22.23.2
python3     3.14.7
Xcode       26.0.1 (17A400)
macOS       15.7.1
skill-up    0.10.0
Chrome      /Applications/Google Chrome.app
```
