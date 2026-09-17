# 订阅追踪器 · 领域层事实纪要（白名单来源）

> 实测环境：macOS 15 / Swift 6.2 Foundation、OpenJDK 17；探针脚本 `/tmp/dateprobe/{probe.swift,money.swift,T.java,M.java}`。
> 白名单内 `developer.android.com/reference/*` 为 JS 渲染，多次抓取仅得导航，故 Android 日期语义以 JDK 实测为准。

## 1 月末裁剪

**两端默认都是"裁剪到月末"，不是进位。**
- iOS `Calendar.date(byAdding:.month,value:1,to:)`：2023-01-31→2023-02-28；2024-01-31→2024-02-29；2023-03-31→2023-04-30；2024-02-29 加 1 年→2025-02-28。[实测]
- `NSCalendar dateByAddingComponents:toDate:options:` 在 options = 0 / wrapComponents / matchPreviousTimePreservingSmallerUnits / matchNextTimePreservingSmallerUnits / matchNextTime / matchStrictly 六种取值下结果**全为 2/28**，即裁剪行为与 options 无关。[实测] 官方文档仅说"未指定 options 时单位溢出进位到更高单位"，并声明"某些运算有歧义、行为依日历而定"，**未**明文说明 1/31+1M 的结果。[来源: https://developer.apple.com/documentation/foundation/nscalendar/date(byadding:to:options:)]
- Android `LocalDate.of(2023,1,31).plusMonths(1)`→2023-02-28；2024-01-31→2024-02-29；`2024-02-29.plusYears(1)`→2025-02-28。[实测]
- **坑：裁剪有损，链式递推会漂移**：`2023-01-31.plusMonths(1).plusMonths(1)`→**2023-03-28**；但从锚点单步 `+13M`→2024-02-29，不漂移。[实测]
- java.time 在 Android 需 API 26+，或 AGP 4.0+ 开启 core library desugaring（官方列明支持 "A subset of `java.time`"）。[来源: https://developer.android.com/studio/write/java8-support]

## 2 金额

- Apple 官方把 `NSDecimalNumber`/`Decimal` 定位为"base-10 算术"类型（mantissa × 10^exponent，mantissa 为最长 38 位十进制整数），并配 `NSDecimalNumberBehaviors`/`NSDecimalNumberHandler` 控制舍入。[来源: https://developer.apple.com/documentation/foundation/nsdecimalnumber]
- 实测误差：Double 累加 12×19.99 = 239.88000000000002（两端结果一致），0.1+0.2 = 0.30000000000000004；整数分累加 12×1999 = 23988 精确；Decimal/BigDecimal 累加 = 239.88 精确。[实测]
- **未找到官方依据**："金额用整数分存储""禁止用 Double 存金额"在两端官方文档均无明文；`NSDecimalNumber` 是否优于 `NSInteger` 分，官方也未做取舍说明。此为社区惯例/推理。

## 3 状态机建模

- Android 官方只在 **UI 层**给出口径：`${Screen}UiState` 可为 data class，"若各状态互斥，也可为 sealed class"；UDF 为 Strongly recommended。[来源: https://developer.android.com/topic/architecture/recommendations]
- Kotlin 官方 enum vs sealed 判据：enum 常量"只存在单一实例"，sealed 子类"可有多个实例"且可各自持有状态；sealed 配 `when` 可编译期穷尽检查、无需 else。[来源: https://kotlinlang.org/docs/sealed-classes.html]
- iOS 官方互斥枚举写法为 `NS_ENUM(NSInteger, Name)`，可组合位掩码用 `NS_OPTIONS(NSUInteger, Name)`；官方理由是显式指定类型与大小、改善 Xcode 补全。[来源: https://developer.apple.com/library/archive/releasenotes/ObjectiveC/ModernizationObjC/AdoptingModernObjective-C/AdoptingModernObjective-C.html]
- **未找到官方依据**：trial/active/expired/canceled 该用"枚举 + 判定函数"还是独立类，官方无规定。

## 4 分层与可测性

- Android 官方：domain layer 是**可选**层，用于"封装复杂业务逻辑，或被多个 ViewModel 复用的简单逻辑"；use case"只负责单一功能、不得含可变数据"、必须 main-safe；命名 = 动词 + 名词 + UseCase；测领域层"典型做法是用 fake repository"。[来源: https://developer.android.com/topic/architecture/domain-layer]
- 测试口径："Know what to test" 与 "Prefer fakes to mocks" 均为 Strongly recommended；ViewModel 不得持有 lifecycle 类型，不传 Activity/Context/Resources。[来源: https://developer.android.com/topic/architecture/recommendations]
- iOS 官方：模型对象"理想情况下不应与展示其数据的视图对象有显式连接——不应关心 UI 与呈现问题"。[来源: https://developer.apple.com/library/archive/documentation/General/Conceptual/DevPedia-CocoaCore/MVC.html]
- XCTest 官方定位单元测试/性能测试/UI 测试三类，UI 交互归 XCUIAutomation；Xcode 16+ 起新单测建议改用 Swift Testing。[来源: https://developer.apple.com/documentation/xctest]

## 5 折月系数

- **未找到官方依据**：4.33 与 52/12 两种系数在两端官方文档中均无规定；二者差异纯属舍入选择，属社区惯例。
- 相邻官方事实：kotlinx-datetime 明确 `LocalDate.plus(DatePeriod)` 按"先年、月，后日"的顺序相加，且 LocalDate 运算与时区无关；但**未**定义月↔周/日的固定换算。[来源: https://kotlinlang.org/api/kotlinx-datetime/kotlinx-datetime/kotlinx.datetime/-local-date/]

---

**白名单内查无**：`developer.android.com/reference/*`（JS 渲染，仅返回导航，未取到 java.time javadoc 原文）；金额存储、折月系数、领域状态机建模三项官方无明文。
