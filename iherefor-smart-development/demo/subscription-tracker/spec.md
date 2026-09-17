# 订阅追踪器（Subscription Tracker）— 需求确认书（阶段 1 产物）

> 生成于 `iherefor-smart-development` skill 阶段 1，闸门 a 已通过（用户确认）。

## 产品定位

记录月费/年费订阅，知道何时扣款、一共花多少钱、免费试用何时到期。

## 技术栈（已定）

- iOS：Objective-C + UIKit + XCTest
- Android：Kotlin + Jetpack Compose + JUnit
- 跨端共享：领域模型 + 数据契约 + 领域规则（语义一致）

## 用户故事（MVP）

| # | 故事 |
|---|---|
| US1 | 作为用户，我想添加一条订阅（名称、金额、周期、下次扣款日），以便记住它 |
| US2 | 作为用户，我想看到订阅列表，看清每条的名称/金额/下次扣款日 |
| US3 | 作为用户，我想看到每月总支出，以便知道订阅一共吃掉多少钱 |
| US4 | 作为用户，我想被提醒即将到期的免费试用，以便在自动扣款前取消 |

## Out of Scope

编辑/删除、排序、云同步、通知推送、多币种、汇率、账户体系、真实支付。

## 领域模型（共享层，两端语义一致）

```
Subscription
├── name: String
├── priceCents: Int          // 固定币种，整数分（避免浮点误差）
├── cycle: BillingCycle      // weekly / monthly / yearly
├── startedAt: Date
├── nextBillingDate: Date    // 由 cycle + startedAt 推导
├── trialEndsAt: Date?       // 可选，免费试用结束日
└── status: SubscriptionStatus  // active / trial / expired / canceled
```

## 核心领域规则（TDD 靶子，纯函数，两端共享语义）

1. `nextBillingDate = startedAt 按 cycle 递推`（周期递推 + 月末裁剪，如 1/31 → 2/28）
2. `status 判定`：trialEndsAt 未过 → trial；已过且未取消 → active；canceled → canceled
3. `每月总支出`：折月求和（weekly×4.33、monthly×1、yearly÷12，取整分或保留约定）
4. `免费试用到期提醒`：未来 N 天（默认 7）内 trialEndsAt 的订阅 → 进入「即将扣款」清单

## 关键决策记录

| 决策 | 结论 |
|---|---|
| 金额表示 | 固定币种 + 整数分（Int cents），月底折算，避免浮点误差 |
| 数据存储 | 内存存储（可注换），Repository 层用内存实现，专注验证领域 + TDD |
| 测试栈 | iOS=XCTest(ObjC)、Android=JUnit；UI 层默认不测，测领域/用例层 |

## 下一步（阶段 2 架构设计）

按 skill 流程：web 白名单搜索（`research` 约束 L1+L2）→ DESIGN-IT-TWICE 并行多案 → 对比择优选方案 → 🔒 闸门 b 人工确认。
