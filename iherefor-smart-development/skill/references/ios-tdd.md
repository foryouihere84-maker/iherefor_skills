# iOS TDD 约定（XCTest / Swift Testing）

面向 `阶段 4 TDD 落地` 的 iOS 侧细则。默认值见 `config/mobile-tdd.json` 的 `ios_defaults`。

## 测试框架选择

> **先确认工程语言**：Swift 与 Objective-C 的测试栈不同，选错会导致测试 target 无法编译。

- **Swift 工程**：新工程 / 部署目标 ≥ iOS 18 优先 **Swift Testing**（`@Test` / `#expect`）；否则用 **XCTest**（`XCTestCase` / `XCTAssert`）。
- **Objective-C 工程**：只能用 **XCTest**（Objective-C 风格 `XCTestCase`）。**Swift Testing 不可用于 ObjC**——`@Test` / `#expect` 是 Swift 专属。
- 不要在同一测试里混用两套断言风格。

## Objective-C 分支（iOS 用 ObjC 时必读）

- **测试 target**：Xcode 里单元测试 target 可以是 ObjC（`.m` 测试文件，`XCTestCase` 子类）。
- **导入被测模块**：用 `#import` 头文件（`#import "Subscription.h"`），而非 Swift 的 `@testable import`。
- **避免 Swift/ObjC 混编测试**：除非工程本身是混编，否则测试与业务代码保持一致语言，减少桥接头文件（Bridging Header）复杂度。
- **断言无差异**：`XCTAssertEqual` / `XCTAssertTrue` 等宏在 ObjC 下照常用。
- **领域逻辑测试要点**：ObjC 里「整数分存储金额」直接对 `NSInteger` 断言，避免 `NSDecimalNumber` 的浮点/比较陷阱；跨端共享的领域规则（月末裁剪、折月求和）在 ObjC 侧用 `NSInteger` + `NSCalendar` 实现并测。

### ObjC 测试 target 的符号链接坑（实测，必读）

**现象**：ObjC 测试文件 `#import` 了领域头文件，但 `xcodebuild test` 链接失败：

```
Undefined symbols for architecture arm64:
  "_OBJC_CLASS_$_STSubscriptionRules", referenced from: ...
```

**根因**：ObjC 的 `.m` 只编进 **app target**，而 unit test 是独立 bundle——它不像 Swift 的 `@testable import` 那样自动看到宿主 app 的符号。测试 bundle 单独编译时 `#import` 只给了声明（头文件），链接时找不到 `.m` 的实现。

**解法（xcodegen 项目）**：让 `project.yml` 的 test target `sources` 把领域源码目录**一并纳入**，使 `.m` 同时编进测试 bundle：

```yaml
SubTrackerTests:
  type: bundle.unit-test
  sources:
    - SubTrackerTests          # 测试文件
    - SubTracker/Domain        # 领域源码也编进测试 bundle（关键！）
  dependencies:
    - target: SubTracker
```

这是 ObjC 逻辑测试（无 TEST_HOST）的标准形态。领域层是纯逻辑、不依赖 UIKit，故可安全双编。**改了 sources 后必须重新 `xcodegen generate`**，新增文件才会进 pbxproj。

## seam 位于何处

- **必测（required）**：领域层 / 用例 / ViewModel。seam 是这些模块的**公开接口**。
- **视情况（conditional）**：Repository（有真实数据源或映射逻辑时）。
- **默认不测**：UI 层。SWiftUI 的 View 层默认不写快照/UI test，除非需求明确要求视觉回归。

## 关键实践

1. **依赖注入、不内部 new**：`init(dependency:)` 接受协议，测试注入 fake。禁止在被测对象内部 `new` 具体依赖。
2. **返回结果、少副作用**：纯函数式可测；副作用函数拆成「计算」与「执行」两段，只测计算段。
3. **Async/await 测试**：XCTest 用 `async` 方法 + `await`；Swift Testing 直接用 `async @Test`。
4. **只测行为不测实现**：断言外部可观察结果，不断言私有属性 / 内部调用顺序。
5. **seam 预确认**：写测试前先把 seam 写下来并和用户确认，未确认的 seam 不写测试。

## 运行与验证

```bash
# 编译 + 单测（workspace 与 scheme、destination 以 ios-environment 探测为准，勿凭记忆手填）
xcodebuild test -workspace <workspace> -scheme <scheme> -destination '<destination>'
```

- 写完一批就跑相关测试文件，全部写完后跑一次完整套件。
- 编译 0 error 是本 skill 的硬门槛；测试 red→green 后进入 code-review。
