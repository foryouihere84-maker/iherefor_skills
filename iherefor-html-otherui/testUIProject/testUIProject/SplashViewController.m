//
//  SplashViewController.m
//  testUIProject
//
//  启屏（启动页）。
//
//  布局契约（闭合方式一览）：
//
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | 背景 | `pinned` 四边贴页面（full-bleed，不自己声明宽高） | — |
//  | Logo 组 | 宽 `equal`（= 品牌文字宽，稿件 114/164 精确相等）；高由子视图闭口 | 水平 `centered`（两稿正中，比值 0.5）；纵向 **`proportional`**：centerY = 页面高 × 0.414319 / 0.392130 |
//  | Logo 图标 | `fixed` 108 / 144（图标点值是视觉常量）；高 `aspect-ratio`（1:1） | 顶贴组顶 `pinned`；组内 `centered` |
//  | 品牌文字 | `intrinsic` 撑开；另加 `bounded` 上限（≤ 页面宽 − 40） | 贴图标底 `pinned` 12 / 13；组内 `centered`；底贴组底 |
//
//  双稿是两套并列独立参考：启屏（393×852），启屏-iPad（810×1080）。
//  文案、字号、图标边长、间距、投影均跨稿分档，非等比放大 —— 见 `usesTabletDesignValues`。
//
//  宽度轴：背景 full-bleed；Logo 组是 `centered` + `equal`，天然不随平板拉宽，
//  不需要另立宽度档。
//

#import "SplashViewController.h"
#import "SplashStyle.h"
#import "WelcomeViewController.h"

@interface SplashViewController ()

// 整页背景图
@property (nonatomic, strong) UIImageView *backgroundView;

// 中心 Logo 组容器（图标 + 文字）
@property (nonatomic, strong) UIView *logoContainer;
@property (nonatomic, strong) UIImageView *logoView;
@property (nonatomic, strong) UILabel *brandLabel;

// Logo 组纵向位置约束（按页面高度比例闭合，比例跨稿分档）
@property (nonatomic, strong, nullable) NSLayoutConstraint *logoGroupCenterYConstraint;
// 已经装上去的比例，用来判断要不要换约束
@property (nonatomic, assign) CGFloat appliedCenterYRatio;

// Logo 尺寸约束（双稿分档，traits 变化时更新）
@property (nonatomic, strong) NSLayoutConstraint *logoSizeConstraint;
// 图标→文字间距约束（双稿分档）
@property (nonatomic, strong) NSLayoutConstraint *logoToTextGapConstraint;

@end

@implementation SplashViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor whiteColor];

    // 背景延伸到状态栏 / 灵动岛下方（underlap），前景居中自然避开。见 runtimeRisks.systemBars。
    // 注意：正是「全屏铺开」让下面的页面高度比例能直接对到设计画布的 852 / 1080。
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    [self buildBackground];
    [self buildLogoGroup];
    [self applyTraits];

    // 启动页点击 → 进入欢迎页
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapSplash:)];
    [self.view addGestureRecognizer:tap];
}

- (void)didTapSplash:(id)sender {
    // TODO: connect business action — 启动页点击进入欢迎页
    WelcomeViewController *welcome = [[WelcomeViewController alloc] init];
    [self.navigationController pushViewController:welcome animated:YES];
}

- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];
    [self applyTraits];
}

- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    // 选稿（iPhone / iPad 两套参考）与字号档变化时同步刷新。
    [self applyTraits];
}

#pragma mark - 选稿分档（双稿 sizeVariants）

/// 当前该用哪一稿的样式常量。
///
/// 这是**选稿**，不是布局决策：双稿（启屏 / 启屏-iPad）是两套并列独立参考，
/// 不存在派生关系，所以要按平台挑一稿的字号 / 边长 / 间距 / 投影。
/// 它的返回值**只喂给样式常量**，绝不参与任何约束的取值 ——
/// 用设备类型去决定「布局怎么收口」才是违规（那叫设备分支，不叫宽度轴）。
- (BOOL)usesTabletDesignValues {
    return self.traitCollection.userInterfaceIdiom == UIUserInterfaceIdiomPad;
}

// 品牌文字文案跨稿分档：iPhone "Color Me AI"，iPad "Pop Color Art"。
- (NSString *)brandText {
    return self.usesTabletDesignValues ? @"Pop Color Art" : @"Color Me AI";
}

// 品牌字号跨稿分档。
- (CGFloat)brandFontSize {
    return self.usesTabletDesignValues ? [SplashStyle brandFontSizeIpad] : [SplashStyle brandFontSizePhone];
}

// Logo 图标边长跨稿分档。
- (CGFloat)logoSize {
    return self.usesTabletDesignValues ? [SplashStyle logoSizeIpad] : [SplashStyle logoSizePhone];
}

// 图标→文字间距跨稿分档。
- (CGFloat)logoToTextGap {
    return self.usesTabletDesignValues ? [SplashStyle logoToTextGapIpad] : [SplashStyle logoToTextGapPhone];
}

// 背景资源跨稿分档。
- (UIImage *)backgroundImage {
    NSString *name = self.usesTabletDesignValues ? @"splash_background_ipad" : @"splash_background";
    return [UIImage imageNamed:name];
}

// Logo 图标资源跨稿分档。
- (UIImage *)logoImage {
    NSString *name = self.usesTabletDesignValues ? @"splash_logo_ipad" : @"splash_logo";
    return [UIImage imageNamed:name];
}

// 把分档值应用到视图与约束。
- (void)applyTraits {
    self.backgroundView.image = [self backgroundImage];
    self.logoView.image = [self logoImage];

    self.brandLabel.attributedText = [self brandAttributedText];

    if (self.logoSizeConstraint) {
        self.logoSizeConstraint.constant = [self logoSize];
    }
    if (self.logoToTextGapConstraint) {
        self.logoToTextGapConstraint.constant = [self logoToTextGap];
    }

    [self applyLogoGroupCenterY];
}

#pragma mark - Logo 组纵向位置（页面高度比例）

/// 装 Logo 组的纵向闭口：`centerY = 页面高 × ratio`。
///
/// 这是 §3.1.1 对**第一层子视图**的要求 —— 纵向位置始终按页面高度比例闭合，
/// 不跟着宽度档走，也不是「居中再挪一个常量」。
///
/// 两个实现约束：`multiplier` 是只读的，比例一变只能**换一条约束**（不能改已存在的那条）；
/// 而且纵向锚点没有 `constraintEqualToAnchor:multiplier:` 这个变体
/// （它只存在于 `NSLayoutDimension`），所以要落到 `constraintWithItem:` 上。
- (void)applyLogoGroupCenterY {
    CGFloat ratio = self.usesTabletDesignValues ? [SplashStyle logoGroupCenterYRatioIpad]
                                                : [SplashStyle logoGroupCenterYRatioPhone];

    if (self.logoGroupCenterYConstraint && fabs(self.appliedCenterYRatio - ratio) < 1e-9) {
        return;   // 比例没变，还是同一条，不重建
    }
    if (self.logoGroupCenterYConstraint) {
        self.logoGroupCenterYConstraint.active = NO;
    }

    // `logoContainer` 是 `self.view` 的直接子视图，共同坐标系就是 `self.view` 自身，
    // 而一个视图在它自己的坐标系里 `bottom` 的值就是它的 `height` ——
    // 于是 `centerY = ratio × view.bottom` 即 `centerY = ratio × 页面高`。
    NSLayoutConstraint *constraint =
        [NSLayoutConstraint constraintWithItem:self.logoContainer
                                    attribute:NSLayoutAttributeCenterY
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:self.view
                                    attribute:NSLayoutAttributeBottom
                                   multiplier:ratio
                                     constant:0.0];
    constraint.active = YES;
    self.logoGroupCenterYConstraint = constraint;
    self.appliedCenterYRatio = ratio;
}

#pragma mark - 品牌文字

/// 品牌文字（手机稿带投影，iPad 稿无）。
///
/// 投影的由来（实时 MCP 回报，缓存快照里查不到）：
/// 手机稿 `shadow = { blurRadius: 0, offsetX: 0, offsetY: 2, color: rgba(86,116,255,0.16) }`；
/// iPad 稿回报里没有 `shadow` 键、`textShadow` 也缺省。
- (NSAttributedString *)brandAttributedText {
    NSMutableDictionary *attrs = [NSMutableDictionary dictionary];

    CGFloat size = [self brandFontSize];
    UIFont *base = [SplashStyle brandFontOfSize:size];
    if (@available(iOS 11.0, *)) {
        // 品牌文字同样要跟随字号档，否则开大字体时它缩在原地、旁边所有页面都在放大。
        base = [[UIFontMetrics metricsForTextStyle:UIFontTextStyleTitle3] scaledFontForFont:base];
    }
    attrs[NSFontAttributeName] = base;
    attrs[NSForegroundColorAttributeName] = [SplashStyle brandTextColor];

    if (!self.usesTabletDesignValues) {
        NSShadow *shadow = [[NSShadow alloc] init];
        shadow.shadowColor = [SplashStyle brandTextShadowColor];
        shadow.shadowOffset = [SplashStyle brandTextShadowOffset];   // (0, 2)
        attrs[NSShadowAttributeName] = shadow;
    }

    NSMutableParagraphStyle *para = [[NSMutableParagraphStyle alloc] init];
    para.alignment = NSTextAlignmentCenter;
    attrs[NSParagraphStyleAttributeName] = para;

    return [[NSAttributedString alloc] initWithString:([self brandText] ?: @"") attributes:attrs];
}

#pragma mark - 背景

- (void)buildBackground {
    self.backgroundView = [[UIImageView alloc] init];
    self.backgroundView.contentMode = UIViewContentModeScaleAspectFill;
    self.backgroundView.clipsToBounds = YES;
    self.backgroundView.userInteractionEnabled = NO;
    self.backgroundView.translatesAutoresizingMaskIntoConstraints = NO;
    self.backgroundView.accessibilityIdentifier = @"splash_background";
    [self.view addSubview:self.backgroundView];

    // `pinned` 四边 —— 背景不声明自己的宽高，由页面给定。
    [NSLayoutConstraint activateConstraints:@[
        [self.backgroundView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [self.backgroundView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.backgroundView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.backgroundView.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor],
    ]];
}

#pragma mark - Logo 组

- (void)buildLogoGroup {
    self.logoContainer = [[UIView alloc] init];
    self.logoContainer.translatesAutoresizingMaskIntoConstraints = NO;
    self.logoContainer.userInteractionEnabled = NO;
    [self.view addSubview:self.logoContainer];

    self.logoView = [[UIImageView alloc] init];
    self.logoView.contentMode = UIViewContentModeScaleAspectFit;
    self.logoView.userInteractionEnabled = NO;
    self.logoView.translatesAutoresizingMaskIntoConstraints = NO;
    self.logoView.accessibilityIdentifier = @"splash_logo";
    [self.logoContainer addSubview:self.logoView];

    self.brandLabel = [[UILabel alloc] init];
    // 稿件是 `whiteSpace: nowrap`（单行）。这里放开换行 + 上面那道 `bounded` 宽度上限，
    // 是因为字号档拉到 AX 档时单行会被截断；放开后是换行而不是掉字。
    self.brandLabel.numberOfLines = 0;
    self.brandLabel.textAlignment = NSTextAlignmentCenter;
    self.brandLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.brandLabel.accessibilityIdentifier = @"splash_brand_text";
    [self.logoContainer addSubview:self.brandLabel];

    // 图标边长是**图标点值尺寸**，属于 `fixed` 视觉常量（跨稿分档 108 / 144），不随窗口缩放。
    self.logoSizeConstraint = [self.logoView.widthAnchor constraintEqualToConstant:[self logoSize]];
    self.logoToTextGapConstraint = [self.brandLabel.topAnchor constraintEqualToAnchor:self.logoView.bottomAnchor
                                                                             constant:[self logoToTextGap]];

    [NSLayoutConstraint activateConstraints:@[
        // 水平：两稿的组都是页面正中（稿件组 centerX 196.5/393、405/810，比值都是 0.5），
        // 所以是 `centered`。
        [self.logoContainer.centerXAnchor constraintEqualToAnchor:self.view.centerXAnchor],

        // 组的宽度由**品牌文字**闭口（`equal`）：稿件 组宽 114 = 文字宽 114、组宽 164 = 文字宽 164，
        // 两稿都精确等于文字宽，而图标（108 / 144）比它窄、在里面居中。
        // 旧代码把组的宽度挂在图标上（`logoView.width == logoContainer.width`），
        // 于是手机组宽被压到 108（文字 114 被截 6pt）、iPad 组宽被压到 144（文字 164 被截 20pt）——
        // 正稿的 iPad「Pop Color Art」会显示成带省略号的残句。
        [self.logoContainer.widthAnchor constraintEqualToAnchor:self.brandLabel.widthAnchor],

        // 组的纵向闭口在 `applyLogoGroupCenterY` 里按页面高度比例装（比例跨稿分档，会换约束）。

        // 图标：`fixed` 边长 + `aspect-ratio` 正方形；顶贴组顶，组内水平居中。
        // 稿件手机稿图标在组内是 2 / 4 的左右留白（非对称 1pt），属手工摆放噪声，按居中处理。
        [self.logoView.topAnchor constraintEqualToAnchor:self.logoContainer.topAnchor],
        [self.logoView.centerXAnchor constraintEqualToAnchor:self.logoContainer.centerXAnchor],
        self.logoSizeConstraint,
        [self.logoView.heightAnchor constraintEqualToAnchor:self.logoView.widthAnchor],

        // 品牌文字：贴图标底（`pinned`，视觉常量 12 / 13），组内居中，底贴组底。
        // 这三条把组高也一并闭口了：手机 108+12+26 = 146、iPad 144+13+34 = 191（稿件实测同值）。
        self.logoToTextGapConstraint,
        [self.brandLabel.centerXAnchor constraintEqualToAnchor:self.logoContainer.centerXAnchor],
        [self.brandLabel.bottomAnchor constraintEqualToAnchor:self.logoContainer.bottomAnchor],
        // `bounded`：字号档拉到很大时给个上限，避免文字宽于页面。
        [self.brandLabel.widthAnchor constraintLessThanOrEqualToAnchor:self.view.widthAnchor constant:-40.0],
    ]];
}

@end
