# Android TDD 约定（JUnit / MockK / Turbine）

面向 `阶段 4 TDD 落地` 的 Android 侧细则。默认值见 `config/mobile-tdd.json` 的 `android_defaults`。

## 测试技术栈

- 单元测试：**JUnit**（JUnit4 或 JUnit5，随工程现状）。
- Mock：**MockK**（Kotlin 惯用，支持 suspend / extension）；老工程用 Mockito 时保持一致。
- Flow 测试：**Turbine** 或 `runTest` + `kotlinx-coroutines-test`。

## seam 位于何处

- **必测（required）**：ViewModel（用 `runTest` 测状态流）、用例 / 领域层纯逻辑。
- **视情况（conditional）**：Repository（有映射/缓存/错误处理逻辑时）、数据源映射。
- **默认不测**：Compose UI 层。UI test / 快照默认不写，除非需求明确要求。

## 关键实践

1. **接口注入**：ViewModel / Repository 依赖接口（`interface`），测试注入 fake；不要在内部 `new` 具体实现。
2. **协程用 runTest**：suspend 函数与 Flow 一律在 `runTest { }` 中测，用 `TestDispatcher` 控制确定性。
3. **MockK 惯用法**：`coEvery { repo.fetch() } returns ...`；`verify` 只验证必要交互，不滥用。
4. **只测行为不测实现**：断言 ViewModel 暴露的状态（`StateFlow.value`），不断言内部字段/调用顺序。
5. **seam 预确认**：写测试前先把 seam 写下来并和用户确认，未确认的 seam 不写测试。

## 运行与验证

```bash
# 单元测试（Gradle task 随模块名，主模块通常是 :app:testDebugUnitTest）
./gradlew test
```

- 写完一批就跑相关测试，全部完后跑一次完整套件。
- Android 端编译（`./gradlew assembleDebug` 或对应 task）0 error 是本 skill 的硬门槛；与 iOS 端**分别**验证。
