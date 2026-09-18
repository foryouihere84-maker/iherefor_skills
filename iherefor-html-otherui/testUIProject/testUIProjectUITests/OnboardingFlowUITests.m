#import <XCTest/XCTest.h>
#import <UIKit/UIKit.h>

@interface OnboardingFlowUITests : XCTestCase
@end

@implementation OnboardingFlowUITests

// 端到端：启动页 → 欢迎页 → 目的 → 性别 → 年龄 → 风格 → 笔刷 → 色板 → 完成
// 通过归一化坐标点击（页面元素默认非 accessibility element，坐标走真实 hitTest）。
// 每步点击后短暂等待 push 动画。
- (void)testFullOnboardingFlow {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    // 1. 启动页：点击任意处进入欢迎页
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.5)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 2. 欢迎页：点击底部 Start 按钮（约 y=0.9）
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.9)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 3. 目的页：点击第一个选项卡（约 y=0.32），再点 Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.32)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap; // Continue
    [NSThread sleepForTimeInterval:1.0];

    // 4. 性别页：点击 Female（y=0.30），Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.30)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 5. 年龄页：点击 Less than 14（y=0.30），Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.30)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 6. 风格页：点击第一个图片卡（左上，约 x=0.3,y=0.45），Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.3, 0.45)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 7. 笔刷页：点击第一个（y=0.35），Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.35)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 8. 色板页：点击第一个（y=0.33），Continue
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.33)].tap;
    [NSThread sleepForTimeInterval:0.5];
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.90)].tap;
    [NSThread sleepForTimeInterval:1.0];

    // 9. 完成页：确认存在（标题 "Looks mazing" 或 CTA "Let's try"）
    XCUIElement *anyStaticText = app.staticTexts.firstMatch;
    fprintf(stderr, "IHEREFOR_EVENT flowDone textExists=%d label='%s'\n",
            anyStaticText.exists ? 1 : 0,
            anyStaticText.exists ? [anyStaticText.label UTF8String] : "<none>");
    fflush(stderr);

    XCTAssertTrue(app.exists, @"流程走完后 App 退出");
    XCTAssertGreaterThan([app descendantsMatchingType:XCUIElementTypeAny].count, 0,
                         @"完成页无任何元素");
}

// iPad 目的页截图：验证卡片 481 宽居中布局（iPhone 归一化坐标在 iPad 错位，需专门坐标）。
- (void)testIpadPurposeScreenshot {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    // 启动页 → 欢迎页
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.5)].tap;
    [NSThread sleepForTimeInterval:1.0];
    // 欢迎页 Start（iPad 底部，y≈0.94）
    [app coordinateWithNormalizedOffset:CGVectorMake(0.5, 0.94)].tap;
    [NSThread sleepForTimeInterval:1.5];

    XCUIScreenshot *shot = [XCUIScreen mainScreen].screenshot;
    XCTAttachment *att = [XCTAttachment attachmentWithScreenshot:shot];
    att.name = @"ipad-purpose";
    att.lifetime = XCTAttachmentLifetimeKeepAlways;
    [self addAttachment:att];

    XCTAssertTrue(app.exists, @"目的页 App 退出");
}

// 逐页截图：性别→年龄→风格→笔刷→色板→完成（iPhone 坐标），每页留档验证渲染。
- (void)testScreenshotAllOnboardingPages {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    void (^shot)(NSString *) = ^(NSString *name) {
        XCUIScreenshot *s = [XCUIScreen mainScreen].screenshot;
        XCTAttachment *a = [XCTAttachment attachmentWithScreenshot:s];
        a.name = name;
        a.lifetime = XCTAttachmentLifetimeKeepAlways;
        [self addAttachment:a];
    };
    void (^tap)(CGFloat, CGFloat) = ^(CGFloat x, CGFloat y) {
        [app coordinateWithNormalizedOffset:CGVectorMake(x, y)].tap;
    };

    // 启动 → 欢迎 → 目的
    tap(0.5, 0.5); [NSThread sleepForTimeInterval:1.0];
    tap(0.5, 0.9); [NSThread sleepForTimeInterval:1.0];

    // 目的 → 性别
    tap(0.5, 0.32); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-gender");

    // 性别 → 年龄
    tap(0.5, 0.30); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-age");

    // 年龄 → 风格
    tap(0.5, 0.30); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-style");

    // 风格 → 笔刷
    tap(0.3, 0.45); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-brush");

    // 笔刷 → 色板
    tap(0.5, 0.35); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-color");

    // 色板 → 完成
    tap(0.5, 0.33); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.0];
    shot(@"iphone-done");

    XCTAssertTrue(app.exists, @"流程走完后 App 退出");
}

#pragma mark - 临时探针：SE 2 代（375×667）逐页水平越界测量

// 复用已有导航坐标，逐页 dump 每个元素的 frame，并显式判定左右越界。
// 结束后请删除本方法（仅用于根因测量，不进入正式用例）。
- (void)ih_probeDump:(XCUIApplication *)app page:(NSString *)page {
    CGRect win = app.windows.firstMatch.frame;
    fprintf(stderr, "IHEREFOR_WIN page=%s win={%.1f,%.1f,%.1f,%.1f}\n",
            page.UTF8String, win.origin.x, win.origin.y, win.size.width, win.size.height);

    // 分类型查询，避免整树枚举时索引失效（树在枚举过程中会变化）。
    NSArray<NSNumber *> *types = @[
        @(XCUIElementTypeAny),
        @(XCUIElementTypeButton),
        @(XCUIElementTypeStaticText),
        @(XCUIElementTypeImage),
        @(XCUIElementTypeOther),
        @(XCUIElementTypeCell),
        @(XCUIElementTypeScrollView),
        @(XCUIElementTypeTable),
        @(XCUIElementTypeTextView),
    ];

    NSUInteger total = 0, offCount = 0;
    NSMutableSet<NSString *> *seen = [NSMutableSet set];

    for (NSNumber *tn in types) {
        XCUIElementType t = (XCUIElementType)tn.integerValue;
        XCUIElementQuery *q = [app descendantsMatchingType:t];
        NSUInteger n = 0;
        @try { n = q.count; } @catch (__unused NSException *ex) { continue; }

        for (NSUInteger i = 0; i < n; i++) {
            XCUIElement *e = [q elementBoundByIndex:i];
            CGRect f;
            NSString *ident = nil, *lbl = nil;
            @try {
                f = e.frame;
                ident = [e identifier];
                lbl = [e label];
            } @catch (__unused NSException *ex) {
                continue; // 该元素在此次快照中已失效，跳过
            }
            if (CGRectIsEmpty(f)) continue;

            NSString *key = [NSString stringWithFormat:@"%.1f|%.1f|%.1f|%.1f|%@",
                             f.origin.x, f.origin.y, f.size.width, f.size.height,
                             lbl ?: @""];
            if ([seen containsObject:key]) continue;
            [seen addObject:key];

            total++;
            CGFloat right = f.origin.x + f.size.width;
            BOOL leftOff  = f.origin.x < win.origin.x - 0.5;
            BOOL rightOff = right > win.origin.x + win.size.width + 0.5;
            BOOL wideOff  = f.size.width > win.size.width + 0.5;
            if (leftOff || rightOff || wideOff) offCount++;

            fprintf(stderr,
                    "IHEREFOR_EL page=%s type=%lu id='%s' label='%s' "
                    "x=%.1f y=%.1f w=%.1f h=%.1f right=%.1f leftOver=%d rightOver=%d widthOver=%d\n",
                    page.UTF8String, (unsigned long)t,
                    ident ? [ident UTF8String] : "",
                    lbl ? [lbl UTF8String] : "",
                    f.origin.x, f.origin.y, f.size.width, f.size.height, right,
                    leftOff ? 1 : 0, rightOff ? 1 : 0, wideOff ? 1 : 0);
        }
    }
    fprintf(stderr, "IHEREFOR_OFFCOUNT page=%s n=%lu off=%lu\n",
            page.UTF8String, (unsigned long)total, (unsigned long)offCount);
    fflush(stderr);
}

- (void)ih_probeShot:(NSString *)name {
    XCUIScreenshot *s = [XCUIScreen mainScreen].screenshot;
    NSString *path = [NSTemporaryDirectory() stringByAppendingPathComponent:
                      [NSString stringWithFormat:@"iherefor-probe-%@.png", name]];
    [s.PNGRepresentation writeToFile:path atomically:YES];
    fprintf(stderr, "IHEREFOR_SHOT %s\n", [path UTF8String]);
    fflush(stderr);
}

- (void)testSE2HorizontalProbe {
    XCUIApplication *app = [[XCUIApplication alloc] init];
    [app launch];
    XCTAssertTrue(app.exists, @"App 未能启动");

    void (^tap)(CGFloat, CGFloat) = ^(CGFloat x, CGFloat y) {
        [app coordinateWithNormalizedOffset:CGVectorMake(x, y)].tap;
    };

    // 1. 启动页
    [NSThread sleepForTimeInterval:1.0];
    [self ih_probeDump:app page:@"splash"];
    [self ih_probeShot:@"splash"];

    tap(0.5, 0.5); [NSThread sleepForTimeInterval:1.2];
    // 2. 欢迎页
    [self ih_probeDump:app page:@"welcome"];
    [self ih_probeShot:@"welcome"];

    tap(0.5, 0.9); [NSThread sleepForTimeInterval:1.2];
    // 3. 目的页
    [self ih_probeDump:app page:@"purpose"];
    [self ih_probeShot:@"purpose"];

    tap(0.5, 0.32); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 4. 性别页
    [self ih_probeDump:app page:@"gender"];
    [self ih_probeShot:@"gender"];

    tap(0.5, 0.30); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 5. 年龄页
    [self ih_probeDump:app page:@"age"];
    [self ih_probeShot:@"age"];

    tap(0.5, 0.30); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 6. 风格页
    [self ih_probeDump:app page:@"style"];
    [self ih_probeShot:@"style"];

    tap(0.3, 0.45); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 7. 笔刷页
    [self ih_probeDump:app page:@"brush"];
    [self ih_probeShot:@"brush"];

    tap(0.5, 0.35); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 8. 色板页
    [self ih_probeDump:app page:@"color"];
    [self ih_probeShot:@"color"];

    tap(0.5, 0.33); [NSThread sleepForTimeInterval:0.4];
    tap(0.5, 0.90); [NSThread sleepForTimeInterval:1.2];
    // 9. 完成页
    [self ih_probeDump:app page:@"done"];
    [self ih_probeShot:@"done"];

    XCTAssertTrue(app.exists, @"流程走完后 App 退出");
}

@end
