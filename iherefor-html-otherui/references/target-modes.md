# 输出模式边界

| 模式 | 语言 | UI 技术 | 首选布局策略 | 比例的表达方式 |
|---|---|---|---|---|
| `ios-swiftui` | Swift | SwiftUI | 声明式容器；重叠区域使用 ZStack/overlay | `GeometryReader` 归一化、`.containerRelativeFrame` |
| `ios-uikit-swift` | Swift | UIKit | Auto Layout + 必要的画布 frame | `NSLayoutConstraint` 的 `multiplier`、`UILayoutGuide` |
| `ios-uikit-objective-c` | Objective-C | UIKit | Auto Layout + 必要的画布 frame | 同上 |
| `android-compose-kotlin` | Kotlin | Jetpack Compose | Box/Row/Column；复杂叠层使用 Box | `BoxWithConstraints` 的 `maxWidth/maxHeight` 派生比例、`weight` |
| `android-views-kotlin` | Kotlin | Android Views/XML | ConstraintLayout/FrameLayout；必要时自定义 View | `layout_constraintGuide_percent`、`bias`、`layout_weight` |
| `android-views-java` | Java | Android Views/XML | ConstraintLayout/FrameLayout；必要时自定义 View | 同上 |

SwiftUI、UIKit Swift 和 UIKit Objective-C 是三个独立输出目标；不能因为它们都在 iOS 上就共享未经验证的生成源码。Android 同理，Compose 与传统 Views/XML 必须分别验证。

所有模式都必须：

- 保留页面真实叠层关系；
- **组件之间的布局关系用比例表达，不得写固定 pt 值**（见 [artifact-contract.md](artifact-contract.md#组件间布局关系必须用比例表达强制)）：位置、间距、容器与图片 frame 的尺寸必须比例化；字号、圆角、描边宽度、最小点击区保持设计值不缩放。禁止用比例缩放字号与最小点击区——那会让 44pt 的点击区在小屏上缩成 40pt；
- 将资源映射为工程内稳定引用；
- 对字体替代、渐变、阴影、SVG、滤镜、动画和 JS 行为记录支持状态；
- 提供关键区域的 accessibility identifier；
- 通过目标平台编译和截图验证。
- 在运行时使用平台尺寸 API 获取真实窗口/根容器尺寸，保存 `runtime-device.json`；禁止使用设备型号对应的固定宽高或截图像素直接作为布局尺寸。

## 系统栏/安全区实现规则

| 平台 | 必须确认 | 常见错误 |
|---|---|---|
| iOS UIKit / SwiftUI | HTML 是否 underlap 状态栏；`edgesForExtendedLayout`、`safeAreaInsets`、状态栏样式、home indicator | 用 safe-area 顶部约束包住整页，导致页面整体下移 |
| Android Compose | `enableEdgeToEdge`、`WindowInsets.statusBars`/`navigationBars`、内容与背景是否分离 | 直接对根 Column 加默认 padding，重复计算 inset |
| Android Views/XML | `WindowCompat.setDecorFitsSystemWindows`、`WindowInsetsCompat`、状态栏/导航栏颜色 | 同时使用 decor fitting 和手工 padding，页面整体下移 |

背景层应按 HTML 事实决定是否延伸到系统栏；文字、按钮等前景层单独应用安全区 inset。该决定必须写入实现计划的 `systemBars` 字段，并在实际截图中验证。
