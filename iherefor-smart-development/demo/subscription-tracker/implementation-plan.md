# 订阅追踪器 · 阶段 3 工程落地计划 + 变更清单

> 依据 `shared-layer.md`（单一事实源），方案 1（三纯函数）。🅻=新增文件，🆁=修改文件。

## 0. 工程现状审计

两端均为刚建的空壳：iOS 有 AppDelegate + 一个空 `SubscriptionListViewController`；Android 有 `MainActivity`（Compose "订阅"文字）。**无既有业务架构、无既有约定可冲突**，故此阶段审计结论为"绿地落地"，专注领域层 + 测试。

## 1. 变更清单 — iOS（Objective-C）

| 操作 | 文件 | 内容 |
|---|---|---|
| 🅻 | `SubTracker/Domain/STSubscription.h/.m` | 值类型：name/priceCents/cycle/startedAt/trialEndsAt，immutable |
| 🅻 | `SubTracker/Domain/STBillingCycle.h` | `NS_ENUM`：weekly/monthly/yearly |
| 🅻 | `SubTracker/Domain/STSubscriptionStatus.h` | `NS_ENUM`：trial/active/expired/canceled |
| 🅻 | `SubTracker/Domain/STFoldPolicy.h/.m` | 折月系数策略（默认 52/12、HALF_UP） |
| 🅻 | `SubTracker/Domain/STSubscriptionRules.h/.m` | 三纯函数 `dueDate/evaluate/summarize`，含月末裁剪 + 锚点单步 |
| 🅻 | `SubTracker/Domain/STDomainError.h` | 错误码：invalidPeriod / invalidPrice / invalidHorizon |
| 🅻 | `SubTracker/Data/InMemorySubscriptionRepository.h/.m` | Repository adapter（`all()`） |
| 🅻 | `SubTrackerTests/STSubscriptionRulesTests.m` | 领域层 XCTest（覆盖 4 条规则 + 漂移陷阱） |

**不新增依赖**（纯 Foundation + XCTest）。测试 target 已存在，直接用。

## 2. 变更清单 — Android（Kotlin）

| 操作 | 文件 | 内容 |
|---|---|---|
| 🅻 | `app/src/main/java/.../domain/Subscription.kt` | data class，字段同共享层 |
| 🅻 | `app/src/main/java/.../domain/BillingCycle.kt` | enum class |
| 🅻 | `app/src/main/java/.../domain/SubscriptionStatus.kt` | enum class |
| 🅻 | `app/src/main/java/.../domain/FoldPolicy.kt` | data class |
| 🅻 | `app/src/main/java/.../domain/SubscriptionRules.kt` | 三纯函数（java.time.LocalDate） |
| 🅻 | `app/src/main/java/.../domain/DomainError.kt` | sealed class |
| 🅻 | `app/src/main/java/.../data/InMemorySubscriptionRepository.kt` | Repository adapter |
| 🅻 | `app/src/test/java/.../SubscriptionRulesTest.kt` | JUnit 单元测试 |
| 🆁 | `app/build.gradle` | 加 `coreLibraryDesugaring` + `isCoreLibraryDesugaringEnabled`（java.time 在 minSdk 24 需要） |

**新增依赖（Gradle）**：
```groovy
compileOptions {
    coreLibraryDesugaringEnabled true
}
dependencies {
    coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.0.4'
}
```

## 3. 跨端对齐（共享层约束落点）

- 两端领域层字段名、不变量、错误语义**严格对齐** `shared-layer.md`。
- 两端测试都必须含：① 月末裁剪（1/31→2/28）；② **链式漂移陷阱**（1/31 起订多期不漂移）；③ 整数分折月精确；④ 状态优先级；⑤ 空列表零汇总。

## 4. UI 层（本轮范围）

- 本轮**只实现领域层 + 测试**，UI 桩保持现状（iOS 空 VC / Android "订阅"文字）。
- US1~US4 的 UI 接线留待领域层验证通过后再做——**这是 TDD 的领域层垂直切片**。

## 5. 回滚方式

- iOS：`xcodegen generate` 可随时重生成工程；新增文件删除即回滚，无跑版风险。
- Android：新增文件删除 + `build.gradle` 去掉 desugaring 三行即回滚。
- 均为绿地新增，无存量破坏。

## 6. 🔒 闸门 c 待批点

以上变更清单（尤其 Android 的 desugaring 依赖、两端领域层文件划分）需你批准后才落码。
