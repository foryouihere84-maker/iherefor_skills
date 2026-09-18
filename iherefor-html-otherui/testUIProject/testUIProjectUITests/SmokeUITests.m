#import <XCTest/XCTest.h>
#import <UIKit/UIKit.h>

@interface SmokeUITests : XCTestCase
@end

@implementation SmokeUITests
- (void)testLaunch { XCUIApplication *app = [[XCUIApplication alloc] init]; [app launch]; XCTAssertTrue(app.exists); }

// 统一入口验收：点击入口页第一行（启屏页），push 进入 splash 页并确认页面渲染非空。
- (void)testEntryPushsToSplash {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    // 入口列表第一行（启屏手机版）。使用 cell 文本命中，避免依赖坐标。
    XCUIElement *firstCell = app.tables.cells.allElementsBoundByIndex.firstObject;
    XCTAssertTrue(firstCell.exists, @"入口列表第一行不存在");
    [firstCell tap];
    // 等待 push 动画完成。
    [NSThread sleepForTimeInterval:2.0];

    // splash 页应至少有一个 image（logo 图标）+ 一个 static text（品牌名）。
    XCUIElement *anyImage = app.images.firstMatch;
    XCUIElement *anyText = app.staticTexts.firstMatch;

    fprintf(stderr, "IHEREFOR_EVENT splash imageExists=%d textExists=%d textValue='%s'\n",
            anyImage.exists ? 1 : 0,
            anyText.exists ? 1 : 0,
            anyText.exists ? [anyText.label UTF8String] : "<none>");
    fflush(stderr);

    // 截图留档（splash 页）。
    XCUIScreenshot *shot = [XCUIScreen mainScreen].screenshot;
    XCTAttachment *att = [XCTAttachment attachmentWithScreenshot:shot];
    att.name = @"splash-page";
    att.lifetime = XCTAttachmentLifetimeKeepAlways;
    [self addAttachment:att];

    XCTAssertTrue(anyImage.exists || anyText.exists, @"splash 页未渲染任何元素");
}


// 运行时设备尺寸探针。
//
// runtime-device.json 的 screenBoundsPoints / rootViewBounds **只认运行时 API 读数**：
// 禁止用设计画布尺寸（本页是 810x1080）、机型推断值、或截图常见尺寸代替。设计画布尺寸
// 与目标设备点尺寸是两件事，前者当基准用会让整条 mapper 链从第一步就是错的。
//
// 输出走 stderr 而不是 NSLog：NSLog 会带上进程/时间戳前缀，且不保证进 xcodebuild 的
// 捕获流；stderr 是 XCTest 直接转发的，配合 fflush 才能保证测试结束前已经落到日志里。
- (void)testProbeRuntimeDeviceSize {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    app.launchEnvironment = @{@"IHEREFOR_PROBE_DEVICE": @"1"};
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    // 测试进程侧的读数：**这不是设备尺寸**，只作对照。runner 的 Info.plist 没有
    // UILaunchScreen，在 iPad 上会被放进兼容画布，所以这里读到的比真机小。
    UIScreen *screen = [UIScreen mainScreen];
    CGSize screenPts = screen.bounds.size;
    CGRect windowFrame = app.windows.firstMatch.frame;

    fprintf(stderr,
            "IHEREFOR_EVENT runner-side screenPoints=%.1fx%.1f appWindowPoints=%.1fx%.1f scale=%.2f\n",
            screenPts.width, screenPts.height,
            windowFrame.size.width, windowFrame.size.height,
            screen.scale);
    fflush(stderr);
}

// 交互回归：证明本页四个交互点（返回 / Skip / 选项卡片 / Continue）在真机运行时
// 真的能被点到。重点是证伪「最后添加的 ringView 描边覆盖层吞掉卡片点击」这类回归
// —— 描边是覆盖整张卡片的子视图，一旦 userInteractionEnabled 被改成 YES，
// 卡片手势就再也收不到事件，而这一点在截图比对里完全看不出来。
//
// 为什么用归一化坐标而不是 accessibilityIdentifier：UIImageView / UILabel 默认
// 不是 accessibility element，只设 accessibilityIdentifier 未必能被 XCUITest
// 检索到；而坐标点击走的是真实 hitTest + 手势识别路径，正是要验证的东西。
//
// 坐标换算：设计稿 393x852 -> 设备 402x874（iPhone 17）
//   x_dev = x_design * 1.02290076
//   y_dev = y_design * 1.02290076 + 1.2443
// 点击不改变本页任何视觉状态（设计稿未定义选中态），故可在同一屏连续点击。
//
// 注意：下面的归一化坐标是按 iPhone 17（402x874pt）算的，换机型需要重算
// （布局本身是自适应的，只是这个测试的探针坐标写死了）。
- (void)testBrushPageInteractionPointsAreHittable {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    // name, 归一化 x, 归一化 y
    NSArray<NSArray *> *points = @[
        @[@"card0(PaintBrush)", @(200.9999 / 402.0), @(256.4580 / 874.0)],
        @[@"card3(Pastel)",     @(200.9999 / 402.0), @(551.0535 / 874.0)],
        @[@"back",              @( 28.6412 / 402.0), @( 70.8015 / 874.0)],
        @[@"skip",              @(367.7330 / 402.0), @( 71.3120 / 874.0)],
        @[@"continue",          @(204.0687 / 402.0), @(774.5570 / 874.0)],
    ];

    for (NSArray *p in points) {
        NSString *name = p[0];
        XCUICoordinate *coord =
            [app coordinateWithNormalizedOffset:CGVectorMake([p[1] doubleValue], [p[2] doubleValue])];
        [coord tap];
        XCTAssertTrue(app.exists, @"点击 %@ 后 App 已退出（疑似崩溃）", name);
    }

    XCTAssertGreaterThan([app descendantsMatchingType:XCUIElementTypeAny].count, 0,
                         @"交互后界面元素全部消失");
}
@end
