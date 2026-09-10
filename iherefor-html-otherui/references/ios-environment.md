# iOS 工程与设备适配协议

不要凭经验拼接 `xcodebuild` 命令。每次 iOS 任务开始时，先运行 `scripts/discover_xcode_environment.py --root <工程根目录>`，把输出保存到当前页面 run 的 `ios-environment.json`，后续命令只使用探测结果中的字段。

## 工程入口选择

优先级：用户明确指定的 `.xcworkspace` 和 scheme；工程根目录唯一的 `.xcworkspace`；唯一 `.xcodeproj`。多候选时停止并记录 `needs-user-choice`，不能猜。workspace 项目必须使用 `-workspace`，不得改用同名 `.xcodeproj`。scheme 必须来自 `xcodebuild -list -json` 的真实输出。

## 设备决策

- 有可启动模拟器且用户允许：优先模拟器，固定 UDID，不使用名称作为唯一标识。
- 只能真机：要求设备 connected、开发者模式/信任状态可用，记录 UDID、OS、架构和签名团队；使用 `-destination id=<UDID>`，不能使用 Simulator destination。
- 无设备或签名不完整：停止在 `environment-blocked`，先修复环境。

真机截图必须使用 `xcrun devicectl` 或 Xcode 设备截图能力，不能把模拟器截图冒充真机证据。每张截图记录 `deviceKind`、UDID、像素尺寸、scale 和采集工具。

## 标准命令模板

路径、scheme、configuration、destination 必须来自 `ios-environment.json`：

```bash
xcodebuild -workspace "$WORKSPACE" -scheme "$SCHEME" -configuration Debug -destination "id=$UDID" -derivedDataPath "$RUN/DerivedData" build
xcodebuild -workspace "$WORKSPACE" -scheme "$SCHEME" -destination "id=$UDID" -derivedDataPath "$RUN/DerivedData" test
```

`.xcodeproj` 只把 `-workspace` 换成 `-project`。真机若需要签名，保留工程签名设置；只有用户明确允许时才使用 `CODE_SIGNING_ALLOWED=NO`，且该结果不能作为真机交付证据。

失败分类为 `入口错误`、`scheme 错误`、`destination/连接错误`、`签名/配置错误`、`编译错误` 或 `测试错误`。同一命令最多自动重试一次，之后停止猜命令并保存诊断。
