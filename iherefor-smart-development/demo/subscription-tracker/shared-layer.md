# 订阅追踪器 · 共享层文档（单一事实源）

> 两端（iOS ObjC / Android Kotlin）落地时**必须以本文件为语义契约**，字段名、不变量、错误模式两端一致。
> 本文件是阶段 2 方案 1 的正式产物，也是阶段 3~5 的共同 spec 源。

## 1. 值类型（语义定义，两端原生映射）

| 概念 | 语义 | iOS 表达 | Android 表达 |
|---|---|---|---|
| Money | 整数分（Int），固定单一币种 | `NSInteger` | `Int` |
| BillingCycle | weekly / monthly / yearly | `NS_ENUM` | `enum class` |
| SubscriptionStatus | trial / active / expired / canceled（互斥） | `NS_ENUM` | `enum class` |
| Subscription | 不可变值：name, priceCents, cycle, startedAt(锚点), trialEndsAt? | Objective-C class（immutable） | `data class`（immutable） |
| FoldPolicy | 折月系数策略，默认 weekly=52/12, monthly=1, yearly=1/12, 舍入 HALF_UP | 结构体/配置对象 | `data class` |

> 金额反例禁止：两端都不得用 Double/Float 或 `NSDecimalNumber` 存金额；统一整数分（已实测 Double 累加 12×19.99=239.88000000000002 有误差）。

## 2. 三个纯函数（领域层接口，方案 1）

这是共享层的全部对外接口。**三函数皆纯函数：无状态、无 I/O、不读系统时钟**（`asOf` 一律由调用方注入）。

### 2.1 `dueDate(anchor, cycle, occurrence) -> Date`

- 语义：从**锚点 `anchor` 单步**递推 `occurrence` 期的日期，`occurrence=0` 返回 anchor 本身。
- **硬约束：锚点单步，禁止链式累加**（防 `1/31 +1M +1M = 3/28` 漂移）。
- 月末裁剪：目标月无该日则裁到该月最后一天（1/31 → 2/28；闰年 2/29 → 2/29）。
- 错误模式：`occurrence < 0` → `DomainError.invalidPeriod`。

### 2.2 `evaluate(subscription, asOf) -> Snapshot`

- 语义：算出一条订阅在 `asOf` 时刻的完整快照。
- Snapshot 字段：`status`、`nextBillingDate`、`monthlyCents`、`trialDaysLeft?`。
- `nextBillingDate` = 最小的、**严格晚于 asOf** 的期次日期（用 dueDate 求）。
- 状态优先级（不可调换顺序）：`canceled > trial >（expired / active）`。
  - `trialEndsAt != null && asOf <= trialEndsAt` → `trial`
  - 否则若已取消 → `canceled`；`canceledAt` 已过且未取消 → `expired`；否则 `active`。

### 2.3 `summarize(subs, asOf, foldPolicy = Default, trialHorizonDays = 7) -> LedgerSummary`

- 语义：把一组订阅汇总成账单概览。
- LedgerSummary 字段：`monthlyTotalCents`、`snapshots[]`（按 nextBillingDate 升序）、`trialEndingSoon[]`（按 trialEndsAt 升序）。
- `monthlyTotalCents` = Σ `evaluate(s).monthlyCents`，只累加 status ∈ {active, trial} 的条目。
- `trialEndingSoon` = status==trial 且 `0 ≤ trialDaysLeft ≤ trialHorizonDays` 的条目。
- 空列表 → 零汇总（非错误）。
- 错误模式：`priceCents < 0` / `horizon < 0` → `DomainError`，**不跨 seam 抛异常**。

## 3. 业务不变量（两端一致）

- I1 `dueDate(a, c, 0) == a`；结果只依赖 (a, c, n)。
- I2 金额全链路整数分；折月只在 `summarize` 内发生一次。
- I3 只有 status==trial 的订阅可进入 `trialEndingSoon`。
- I4 折月：weekly×52/12、monthly×1、yearly×1/12，结果 HALF_UP 舍入到分。

## 4. 数据契约（Repository seam）

- Repository 接口仅 `all() -> [Subscription]`（MVP 最小）。
- 现用 `InMemoryRepository` adapter；未来本地/云存储各写 adapter，领域层不动。
- 时钟通过 `asOf` 参数注入，领域层**永不**调用 `now()`/`Date()`。

## 5. 分叉点（两端各自落地，语义对齐但实现不同）

| 维度 | iOS（Objective-C） | Android（Kotlin） |
|---|---|---|
| 日期递推 | `NSCalendar dateByAddingComponents` | `java.time.LocalDate.plusMonths/plusYears`（API 26+ 或 desugaring） |
| 状态机 | `NS_ENUM(NSInteger)` | `enum class` |
| 折月系数 | 配置结构体 | `data class FoldPolicy` |
| 测试 | XCTest（ObjC） | JUnit |
| 存储 | `InMemorySubscriptionRepository`（ObjC） | `InMemorySubscriptionRepository`（Kotlin） |

### 已知平台差异（必须在两端各自测试中覆盖）

- iOS 与 Android 的月末裁剪**默认行为一致**（裁剪不进位），但**链式递推漂移**是共性陷阱 → 两端测试都必须含"1/31 起订、递推多期不漂移"用例。
- Android `java.time` 需注意 minSdk 24 → 依赖 desugaring（见 `references/ios-tdd.md` / 事实纪要）。
