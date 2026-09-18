//
//  OnboardingBaseViewController.m
//  testUIProject
//
//  引导流程骨架实现。
//
//  **每个元素写清「由谁闭合」**（设计值只是参考事实，不等于生产约束）：
//
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | 背景装饰图 | `aspect-ratio`（位图自身比例） | 贴父三边（`pinned`，full-bleed） |
//  | 返回键 | `fixed` 32/44 + 1:1（`aspect-ratio`） | 贴安全区左上（`pinned` 12/48、8） |
//  | 进度条轨道 | 高 `fixed` 6/8；宽 `proportional` 0.5903×页面宽 | 居中 + 与返回键 centerY 对齐（`centered`） |
//  | 进度条填充 | 宽 `proportional` × 轨道宽 | 贴轨道三边（`pinned`） |
//  | Skip | `intrinsic`（文字撑开） | 贴安全区右（`pinned` 20/40）+ 与返回键 centerY 对齐 |
//  | 标题 | `intrinsic` 高；宽 `bounded`（内容列） | 贴返回键底 `pinned` 24/29 |
//  | 选项列表 | `intrinsic` 高（子类内容撑开） | 贴标题底 `pinned` 69/87 |
//  | CTA | 高 `bounded`（>= 56/75，内容可撑高）；宽 `bounded` 封顶 480 | 贴安全区底 `pinned` 34/81 + 居中 |
//
//  **不再出现的东西**（都是旧口径的残留）：
//  - `equalToConstant 353/481/347` —— 把「在一台设备上量到的宽度」当成常量；
//    在 iPad 分屏（~320pt）上 481 会直接溢出。改成内边距闭合 + 封顶。
//  - `equalToConstant 232/482` 进度条宽 —— 两稿比例一致到 0.8%，是比例关系。
//  - 「24+28=52」状态栏高度补偿 —— 把某个机型的 44pt 当成常量。
//  - `contentWidth` 这类「设备分档的宽度」—— 宽度归宽度轴，不归设备。
//

#import "OnboardingBaseViewController.h"
#import "OnboardingDoneViewController.h"

@interface OnboardingBaseViewController ()

@property (nonatomic, assign) OnboardingWidthClass widthClass;

@property (nonatomic, strong) UIView *backgroundView;
@property (nonatomic, strong) NSLayoutConstraint *backgroundRatioConstraint;

@property (nonatomic, strong) UIButton *backButton;
@property (nonatomic, strong) UIButton *skipButton;

@property (nonatomic, strong) UIView *progressTrackView;
@property (nonatomic, strong) UIView *progressFillView;
@property (nonatomic, strong) NSLayoutConstraint *progressWidthConstraint;
@property (nonatomic, strong) NSLayoutConstraint *progressFillWidthConstraint;

@property (nonatomic, strong, readwrite) UILabel *titleLabel;

@property (nonatomic, strong) UIScrollView *optionScrollView;
@property (nonatomic, strong, readwrite) UIView *optionContainer;

@property (nonatomic, strong) UIView *footerScrimView;
@property (nonatomic, strong) UIButton *continueButton;
@property (nonatomic, strong) UIImageView *ctaArrowView;
@property (nonatomic, strong) NSLayoutConstraint *ctaArrowSizeConstraint;
@property (nonatomic, strong) NSLayoutConstraint *ctaArrowRightConstraint;

// 「宽度收敛」的三件套：内边距（pinned） + 封顶（bounded） + 居中（centered）。
// 内容列与 CTA 各一份，手机档下封顶永不生效（353/347 < 481/480）。
@property (nonatomic, strong) NSLayoutConstraint *contentCapConstraint;
@property (nonatomic, strong) NSLayoutConstraint *ctaCapConstraint;

@end

@implementation OnboardingBaseViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [OnboardingStyle pageBackground];
    // 内容铺到系统栏下方：顶部栏与底部 CTA 都贴**安全区**，不贴物理屏幕边缘。
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    // 选稿：双稿按**设备平台**取（与窗口宽度无关，宽度档只管横向收敛）。
    // 不在这里缓存成 ivar —— 唯一来源是 `usesTabletDesignValues`（子类可重写），
    // 缓存一份会让子类的重写对基类自己的 token 失效（两套选稿结果）。
    self.widthClass = [OnboardingStyle widthClassForWindowWidth:self.view.bounds.size.width];

    [self buildBackground];
    [self buildTopBar];
    [self buildTitle];
    [self buildContinueCTA];
    [self buildOptionList];   // 列表的下边界要让位于 CTA，必须在 CTA 之后建
    [self buildFooterScrim];

    [self buildOptions];
    [self applyWidthClass];
}

// 窗口宽度变了就重算宽度档：iPad 分屏 1/3、Slide Over、Stage Manager 都会走到这里。
// iOS 17+ 可用 `registerForTraitChanges:` 替代本回调；本回调在 17 上仍受支持。
- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    if (!CGSizeEqualToSize(self.view.bounds.size, (CGSize){0, 0})) {
        self.widthClass = [OnboardingStyle widthClassForWindowWidth:self.view.bounds.size.width];
    }
    [self applyWidthClass];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    // CTA 高由 `>=` 闭合、可被内容撑高，胶囊圆角必须跟着实际高度算，不能在 viewDidLoad 里定死。
    self.continueButton.layer.cornerRadius = CGRectGetHeight(self.continueButton.bounds) / 2.0;
    self.progressTrackView.layer.cornerRadius = CGRectGetHeight(self.progressTrackView.bounds) / 2.0;
    self.progressFillView.layer.cornerRadius = CGRectGetHeight(self.progressFillView.bounds) / 2.0;
}

#pragma mark - 宽度轴

/// 宽度档下的横向收敛。**水平轴按宽度档收口；垂直轴不参与** ——
/// 垂直位置一律贴安全区边（`pinned`），短屏 / 横屏下 CTA 与顶部栏都不会被挤出去。
- (void)applyWidthClass {
    OnboardingWidthClass widthClass = self.widthClass;

    if (widthClass == OnboardingWidthClassCompact) {
        // compact：内容列由 20/20 内边距闭合，封顶（481）永不生效；
        // 这一档的视觉与设计稿逐字一致，不引入任何额外规则。
    } else {
        // medium / expanded：内容列改由封顶（`maxContentWidth`）收口并居中 ——
        // 内边距约束此时退化为 `>=` / `<=` 下界，不参与决定宽度。
        // 当前没有需要在这里重排的结构（列数的档差在子类里按宽度档取）。
    }

    // 封顶值随页面内容列变化（风格页 3 列网格 640）。手机档下 353/347 < 481/480，永不触发。
    if (self.contentCapConstraint) {
        self.contentCapConstraint.constant = [self maxContentWidth];
    }
    [self.view setNeedsLayout];
}

#pragma mark - 选稿 / 子类默认值

- (BOOL)usesTabletDesignValues {
    return self.traitCollection.userInterfaceIdiom == UIUserInterfaceIdiomPad;
}

- (NSString *)titleText { return @""; }
- (NSAttributedString *)titleAttributedText { return nil; }
- (NSString *)ctaText { return @"Continue"; }
- (Class)nextViewControllerClass { return Nil; }

- (CGFloat)titleFontSize {
    return self.usesTabletDesignValues ? [OnboardingStyle titleFontSizeIpad] : [OnboardingStyle titleFontSizePhone];
}
- (CGFloat)maxContentWidth { return [OnboardingStyle maxContentWidth]; }
- (CGFloat)optionCardHeight {
    return self.usesTabletDesignValues ? [OnboardingStyle optionCardHeightIpad] : [OnboardingStyle optionCardHeightPhone];
}
- (CGFloat)ctaHeight {
    return self.usesTabletDesignValues ? [OnboardingStyle ctaHeightIpad] : [OnboardingStyle ctaHeightPhone];
}

#pragma mark - 背景装饰图（full-bleed + aspect-ratio）

// 高度由**位图自身宽高比**闭合：手机 393×365 → 365/393；iPad 810×396 → 396/810。
// 两稿比例不同（1.0767 vs 2.0455），但各自的比例都写在资源里，
// 所以既不用 365/396 这类跨稿常量，也不会在窄窗口上拉伸变形。
- (void)buildBackground {
    UIImage *image = [UIImage imageNamed:(self.usesTabletDesignValues ? @"onboarding_bg_ipad" : @"onboarding_bg_phone")];

    self.backgroundView = [[UIImageView alloc] initWithImage:image];
    self.backgroundView.contentMode = UIViewContentModeScaleAspectFill;
    self.backgroundView.clipsToBounds = YES;
    self.backgroundView.userInteractionEnabled = NO;
    self.backgroundView.translatesAutoresizingMaskIntoConstraints = NO;
    self.backgroundView.accessibilityIdentifier = @"onboarding_background";
    [self.view insertSubview:self.backgroundView atIndex:0];

    CGFloat ratio = (image.size.width > 0) ? (image.size.height / image.size.width) : (365.0 / 393.0);
    self.backgroundRatioConstraint =
        [self.backgroundView.heightAnchor constraintEqualToAnchor:self.backgroundView.widthAnchor multiplier:ratio];

    [NSLayoutConstraint activateConstraints:@[
        [self.backgroundView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [self.backgroundView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.backgroundView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        self.backgroundRatioConstraint,
    ]];
}

#pragma mark - 顶部栏（贴安全区 + 对齐锚点）

- (CGFloat)topBarTopInset { return [OnboardingStyle topBarTopInset]; }
- (CGFloat)backButtonLeading {
    return self.usesTabletDesignValues ? [OnboardingStyle backButtonLeadingIpad] : [OnboardingStyle backButtonLeadingPhone];
}
- (CGFloat)skipRightInset {
    return self.usesTabletDesignValues ? [OnboardingStyle skipRightInsetIpad] : [OnboardingStyle skipRightInsetPhone];
}
- (CGFloat)titleTopGap {
    return self.usesTabletDesignValues ? [OnboardingStyle titleTopGapIpad] : [OnboardingStyle titleTopGapPhone];
}
- (CGFloat)contentTopGap {
    return self.usesTabletDesignValues ? [OnboardingStyle contentTopGapIpad] : [OnboardingStyle contentTopGapPhone];
}
- (CGFloat)ctaBottomInset {
    return self.usesTabletDesignValues ? [OnboardingStyle ctaBottomInsetIpad] : [OnboardingStyle ctaBottomInsetPhone];
}

- (void)buildTopBar {
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    CGFloat backSize = self.usesTabletDesignValues ? [OnboardingStyle backButtonSizeIpad] : [OnboardingStyle backButtonSizePhone];
    CGFloat progressHeight = self.usesTabletDesignValues ? [OnboardingStyle progressHeightIpad] : [OnboardingStyle progressHeightPhone];
    CGFloat skipFontSize = self.usesTabletDesignValues ? [OnboardingStyle skipFontSizeIpad] : [OnboardingStyle skipFontSizePhone];

    self.backButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.backButton setImage:[UIImage systemImageNamed:@"chevron.left"] forState:UIControlStateNormal];
    self.backButton.tintColor = [OnboardingStyle titleColor];
    [self.backButton addTarget:self action:@selector(didTapBack:) forControlEvents:UIControlEventTouchUpInside];
    self.backButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.backButton.accessibilityIdentifier = @"onboarding_back";
    [self.view addSubview:self.backButton];

    self.progressTrackView = [[UIView alloc] init];
    self.progressTrackView.backgroundColor = [OnboardingStyle progressTrack];
    self.progressTrackView.clipsToBounds = YES;
    self.progressTrackView.translatesAutoresizingMaskIntoConstraints = NO;
    self.progressTrackView.accessibilityIdentifier = @"onboarding_progress";
    [self.view addSubview:self.progressTrackView];

    self.progressFillView = [[UIView alloc] init];
    self.progressFillView.backgroundColor = [OnboardingStyle progressFill];
    self.progressFillView.clipsToBounds = YES;
    self.progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
    [self.progressTrackView addSubview:self.progressFillView];

    self.skipButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.skipButton setTitle:@"Skip" forState:UIControlStateNormal];
    [self.skipButton setTitleColor:[OnboardingStyle titleColor] forState:UIControlStateNormal];
    self.skipButton.titleLabel.adjustsFontForContentSizeCategory = YES;
    self.skipButton.titleLabel.font =
        [OnboardingStyle scaledFont:[OnboardingStyle optionFontOfSize:skipFontSize] forTextStyle:UIFontTextStyleBody];
    [self.skipButton addTarget:self action:@selector(didTapSkip:) forControlEvents:UIControlEventTouchUpInside];
    self.skipButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.skipButton.accessibilityIdentifier = @"onboarding_skip";
    [self.view addSubview:self.skipButton];

    // 返回键：位置贴安全区左上（pinned，常量是设计稿给的边距）；尺寸 fixed + 1:1。
    // 顶部偏移取**单一设计常量 8**（两稿同为「状态栏下方 8pt」），
    // 不按机型状态栏高度补偿 —— 见 OnboardingStyle.topBarTopInset 的说明。
    self.progressWidthConstraint =
        [self.progressTrackView.widthAnchor constraintEqualToAnchor:safe.widthAnchor
                                                          multiplier:[OnboardingStyle progressWidthRatio]];
    self.progressFillWidthConstraint = [self progressFillConstraintWithFraction:[self progressFraction]];

    [NSLayoutConstraint activateConstraints:@[
        [self.backButton.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:self.backButtonLeading],
        [self.backButton.topAnchor constraintEqualToAnchor:safe.topAnchor constant:[self topBarTopInset]],
        [self.backButton.widthAnchor constraintEqualToConstant:backSize],
        [self.backButton.heightAnchor constraintEqualToAnchor:self.backButton.widthAnchor],

        // 进度条：水平居中于安全区（centered），纵向与返回键对齐（§3.3 对齐优先于算位置）。
        [self.progressTrackView.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [self.progressTrackView.centerYAnchor constraintEqualToAnchor:self.backButton.centerYAnchor],
        self.progressWidthConstraint,
        [self.progressTrackView.heightAnchor constraintEqualToConstant:progressHeight],

        [self.progressFillView.leadingAnchor constraintEqualToAnchor:self.progressTrackView.leadingAnchor],
        [self.progressFillView.topAnchor constraintEqualToAnchor:self.progressTrackView.topAnchor],
        [self.progressFillView.bottomAnchor constraintEqualToAnchor:self.progressTrackView.bottomAnchor],
        self.progressFillWidthConstraint,

        // Skip 宽由文字撑开（intrinsic），不写宽度常量。
        [self.skipButton.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-self.skipRightInset],
        [self.skipButton.centerYAnchor constraintEqualToAnchor:self.backButton.centerYAnchor],
    ]];

    // 终点页（引导完成）把这三个都收起来 —— 稿件里该页没有顶部栏。
    // 子类在 `viewDidLoad` 里先设 `hidesBackAndSkip` 再调 `super`，所以这里已经是最终值。
    [self applyTopBarVisibility];
}

/// 进度填充宽度 = 轨道宽度 × 进度值（`proportional`，基准是直接父视图 = 轨道）。
/// 不写成「轨道宽 × 进度值」算出来的一次性字面量 —— 那样轨道变宽时填充不会跟着变。
- (CGFloat)progressFraction {
    return self.totalSteps > 0 ? (CGFloat)self.stepIndex / (CGFloat)self.totalSteps : 0.0;
}

- (NSLayoutConstraint *)progressFillConstraintWithFraction:(CGFloat)fraction {
    return [self.progressFillView.widthAnchor constraintEqualToAnchor:self.progressTrackView.widthAnchor
                                                           multiplier:MAX(fraction, 0.0001)];
}

- (void)setProgressFraction:(CGFloat)fraction {
    self.progressFillWidthConstraint.active = NO;
    self.progressFillWidthConstraint =
        [self.progressFillView.widthAnchor constraintEqualToAnchor:self.progressTrackView.widthAnchor
                                                        multiplier:MAX(fraction, 0.0001)];
    self.progressFillWidthConstraint.active = YES;
}

#pragma mark - 标题（宽由内容列闭合，高由内容撑开）

- (void)buildTitle {
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    UILayoutGuide *readable = self.view.readableContentGuide;

    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.numberOfLines = 0;
    self.titleLabel.textColor = [OnboardingStyle titleColor];
    self.titleLabel.textAlignment = NSTextAlignmentCenter;
    self.titleLabel.adjustsFontForContentSizeCategory = YES;
    self.titleLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.titleLabel.accessibilityIdentifier = @"onboarding_title";
    [self.view addSubview:self.titleLabel];

    if ([self titleAttributedText]) {
        self.titleLabel.attributedText = [self titleAttributedText];
    } else {
        self.titleLabel.text = self.titleText;
        self.titleLabel.font =
            [OnboardingStyle scaledFont:[OnboardingStyle titleFontOfSize:[self titleFontSize]]
                            forTextStyle:UIFontTextStyleTitle1];
    }

    // 宽度：两侧内边距闭合（`pinned` 20）+ 居中；`readableContentGuide` 作为可读宽度的下界，
    // 只在系统字号极大时生效（那一刻把长标题收进可读列，比让它铺满更可读）。
    NSLayoutConstraint *full = [self.titleLabel.widthAnchor constraintEqualToAnchor:safe.widthAnchor constant:-40.0];
    full.priority = UILayoutPriorityDefaultHigh;

    [NSLayoutConstraint activateConstraints:@[
        // 纵向闭口由子类可重写的 `titleTopConstraint` 提供（默认贴返回键底）。
        [self titleTopConstraint],
        [self.titleLabel.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [self.titleLabel.leadingAnchor constraintGreaterThanOrEqualToAnchor:safe.leadingAnchor constant:20.0],
        [self.titleLabel.trailingAnchor constraintLessThanOrEqualToAnchor:safe.trailingAnchor constant:-20.0],
        [self.titleLabel.leadingAnchor constraintGreaterThanOrEqualToAnchor:readable.leadingAnchor],
        [self.titleLabel.trailingAnchor constraintLessThanOrEqualToAnchor:readable.trailingAnchor],
        full,
    ]];
}

/// 默认：标题顶贴返回键底（`pinned`，常量 24/29）。
/// **引导完成页重写本方法**，改为按页面高度比例闭合 —— 该页没有顶部栏。
- (NSLayoutConstraint *)titleTopConstraint {
    return [self.titleLabel.topAnchor constraintEqualToAnchor:self.backButton.bottomAnchor
                                                     constant:self.titleTopGap];
}

#pragma mark - 选项列表（可滚动，短屏 / 大字号下不缺失）

// 为什么是滚动容器：设计稿里手机 6 张 66pt 卡片、iPad 6 张，都是按 393×852 / 810×1080 排的。
// 换到 iPhone SE（375×667，安全区顶仅 20pt）时，固定排布会把最后一张卡片压到 CTA 下面 ——
// 这就是「较短手机纵向 UI 部分缺失」。列表高度改为「上贴标题、下让位于 CTA」，
// 内容超了就滚，设计机型上内容装得下，所以视觉与稿件逐字一致。
- (void)buildOptionList {
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    UILayoutGuide *readable = self.view.readableContentGuide;

    self.optionScrollView = [[UIScrollView alloc] init];
    self.optionScrollView.translatesAutoresizingMaskIntoConstraints = NO;
    self.optionScrollView.showsVerticalScrollIndicator = NO;
    self.optionScrollView.alwaysBounceVertical = NO;
    // 容器已经贴在安全区内，不需要再自动加内边距（否则安全区被算两次）。
    self.optionScrollView.contentInsetAdjustmentBehavior = UIScrollViewContentInsetAdjustmentNever;
    self.optionScrollView.accessibilityIdentifier = @"onboarding_options";
    [self.view addSubview:self.optionScrollView];

    self.optionContainer = [[UIView alloc] init];
    self.optionContainer.translatesAutoresizingMaskIntoConstraints = NO;
    [self.optionScrollView addSubview:self.optionContainer];

    // **内容列**：宽度由两侧 20pt 内边距闭合（pinned） + 封顶 maxContentWidth（bounded，481/640）
    // + 居中（centered）。手机档下封顶永不生效；宽档下内边距退化为下界、由封顶决定宽度。
    self.contentCapConstraint =
        [self.optionScrollView.widthAnchor constraintLessThanOrEqualToConstant:[self maxContentWidth]];

    NSLayoutConstraint *contentFull =
        [self.optionScrollView.widthAnchor constraintEqualToAnchor:safe.widthAnchor constant:-2 * [OnboardingStyle contentHorizontalInset]];
    contentFull.priority = UILayoutPriorityDefaultHigh;

    NSLayoutConstraint *listBottom =
        [self.optionScrollView.bottomAnchor constraintEqualToAnchor:self.continueButton.topAnchor
                                                           constant:-[OnboardingStyle listToCTAMinGap]];
    listBottom.priority = UILayoutPriorityDefaultHigh;   // 与「高度 >= 44」冲突时让位，不产生 broken constraint

    [NSLayoutConstraint activateConstraints:@[
        // 上贴标题底（pinned 69/87）—— 第一层子视图的纵向位置锚在兄弟元素上，不写探针设备绝对坐标。
        [self.optionScrollView.topAnchor constraintEqualToAnchor:self.titleLabel.bottomAnchor constant:self.contentTopGap],
        [self.optionScrollView.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [self.optionScrollView.leadingAnchor constraintGreaterThanOrEqualToAnchor:safe.leadingAnchor
                                                                        constant:[OnboardingStyle contentHorizontalInset]],
        [self.optionScrollView.trailingAnchor constraintLessThanOrEqualToAnchor:safe.trailingAnchor
                                                                       constant:-[OnboardingStyle contentHorizontalInset]],
        [self.optionScrollView.leadingAnchor constraintGreaterThanOrEqualToAnchor:readable.leadingAnchor],
        [self.optionScrollView.trailingAnchor constraintLessThanOrEqualToAnchor:readable.trailingAnchor],
        self.contentCapConstraint,
        contentFull,
        [self.optionScrollView.heightAnchor constraintGreaterThanOrEqualToConstant:44.0],
        listBottom,

        // 容器铺满滚动内容区；高度由子类内容撑开（子类把最后一项的 bottom 贴到容器 bottom）。
        [self.optionContainer.topAnchor constraintEqualToAnchor:self.optionScrollView.contentLayoutGuide.topAnchor],
        [self.optionContainer.leadingAnchor constraintEqualToAnchor:self.optionScrollView.contentLayoutGuide.leadingAnchor],
        [self.optionContainer.trailingAnchor constraintEqualToAnchor:self.optionScrollView.contentLayoutGuide.trailingAnchor],
        [self.optionContainer.bottomAnchor constraintEqualToAnchor:self.optionScrollView.contentLayoutGuide.bottomAnchor],
        [self.optionContainer.widthAnchor constraintEqualToAnchor:self.optionScrollView.frameLayoutGuide.widthAnchor],
    ]];
}

#pragma mark - 底部遮罩（长列表滚过 CTA 时用）

- (void)buildFooterScrim {
    self.footerScrimView = [[UIView alloc] init];
    self.footerScrimView.backgroundColor = [OnboardingStyle footerScrim];
    self.footerScrimView.userInteractionEnabled = NO;
    self.footerScrimView.hidden = !self.showsFooterScrim;
    self.footerScrimView.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view insertSubview:self.footerScrimView aboveSubview:self.optionScrollView];

    [NSLayoutConstraint activateConstraints:@[
        [self.footerScrimView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.footerScrimView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.footerScrimView.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor],
        [self.footerScrimView.topAnchor constraintEqualToAnchor:self.continueButton.topAnchor constant:-66.0],
    ]];
}

#pragma mark - Continue CTA

- (void)buildContinueCTA {
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;

    self.continueButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.continueButton setTitle:[self ctaText] forState:UIControlStateNormal];
    [self.continueButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    self.continueButton.titleLabel.adjustsFontForContentSizeCategory = YES;
    self.continueButton.titleLabel.font = [self ctaFont];
    self.continueButton.clipsToBounds = YES;
    self.continueButton.backgroundColor = [OnboardingStyle accent];
    [self.continueButton addTarget:self action:@selector(didTapContinue:) forControlEvents:UIControlEventTouchUpInside];
    self.continueButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.continueButton.accessibilityIdentifier = @"onboarding_continue";
    [self.view addSubview:self.continueButton];

    // CTA 右侧箭头：paint_icon_close 与 onboarding_cta_arrow 是同一个图形的两个命名，
    // 生产用切图资源 onboarding_cta_arrow（32/44）。
    self.ctaArrowView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:@"onboarding_cta_arrow"]];
    self.ctaArrowView.contentMode = UIViewContentModeScaleAspectFit;
    self.ctaArrowView.userInteractionEnabled = NO;
    self.ctaArrowView.translatesAutoresizingMaskIntoConstraints = NO;
    [self.continueButton addSubview:self.ctaArrowView];

    // 宽：两侧 23 内边距闭合（pinned） + 封顶 480（bounded） + 居中（centered）。
    // 高：`>=` 闭合（bounded）—— 设计值 56/75 是下限，动态字体放大时按钮可以变高而不是裁字。
    self.ctaCapConstraint = [self.continueButton.widthAnchor constraintLessThanOrEqualToConstant:[OnboardingStyle ctaMaxWidth]];
    self.ctaArrowSizeConstraint =
        [self.ctaArrowView.widthAnchor constraintEqualToConstant:
            (self.usesTabletDesignValues ? [OnboardingStyle ctaArrowSizeIpad] : [OnboardingStyle ctaArrowSizePhone])];
    self.ctaArrowRightConstraint =
        [self.ctaArrowView.trailingAnchor constraintEqualToAnchor:self.continueButton.trailingAnchor
                                                         constant:-(self.usesTabletDesignValues ? [OnboardingStyle ctaArrowRightInsetIpad]
                                                                                     : [OnboardingStyle ctaArrowRightInsetPhone])];

    NSLayoutConstraint *ctaFull =
        [self.continueButton.widthAnchor constraintEqualToAnchor:safe.widthAnchor
                                                       constant:-2 * [OnboardingStyle ctaHorizontalInset]];
    ctaFull.priority = UILayoutPriorityDefaultHigh;

    [NSLayoutConstraint activateConstraints:@[
        [self.continueButton.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-self.ctaBottomInset],
        [self.continueButton.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [self.continueButton.leadingAnchor constraintGreaterThanOrEqualToAnchor:safe.leadingAnchor
                                                                      constant:[OnboardingStyle ctaHorizontalInset]],
        [self.continueButton.trailingAnchor constraintLessThanOrEqualToAnchor:safe.trailingAnchor
                                                                     constant:-[OnboardingStyle ctaHorizontalInset]],
        [self.continueButton.heightAnchor constraintGreaterThanOrEqualToConstant:[self ctaHeight]],
        self.ctaCapConstraint,
        ctaFull,

        self.ctaArrowRightConstraint,
        [self.ctaArrowView.centerYAnchor constraintEqualToAnchor:self.continueButton.centerYAnchor],
        self.ctaArrowSizeConstraint,
        [self.ctaArrowView.heightAnchor constraintEqualToAnchor:self.ctaArrowView.widthAnchor],
    ]];
}

- (UIFont *)ctaFont {
    CGFloat size = self.usesTabletDesignValues ? [OnboardingStyle ctaFontSizeIpad] : [OnboardingStyle ctaFontSizePhone];
    return [OnboardingStyle scaledFont:[OnboardingStyle ctaFontOfSize:size] forTextStyle:UIFontTextStyleTitle3];
}

#pragma mark - 状态

- (void)setHasSelection:(BOOL)hasSelection {
    _hasSelection = hasSelection;
    [self updateContinueState];
}

- (void)setShowsFooterScrim:(BOOL)showsFooterScrim {
    _showsFooterScrim = showsFooterScrim;
    self.footerScrimView.hidden = !showsFooterScrim;
}

- (void)setHidesBackAndSkip:(BOOL)hidesBackAndSkip {
    _hidesBackAndSkip = hidesBackAndSkip;
    [self applyTopBarVisibility];
}

/// 终点页（引导完成）没有顶部栏：返回键 / 进度条 / Skip 三个一起收起来。
/// **只隐藏、不删除** —— 标题默认的纵向闭口挂在返回键底边上，
/// 真把它从视图树里摘掉会连带断掉那条约束。
- (void)applyTopBarVisibility {
    BOOL hidden = self.hidesBackAndSkip;
    self.backButton.hidden = hidden;
    self.progressTrackView.hidden = hidden;
    self.skipButton.hidden = hidden;
}

- (void)updateContinueState {
    // 有标题但无需选择的页（如引导完成）始终可用；其余页必须有选择。
    self.continueButton.enabled = self.hasSelection || self.stepIndex == self.totalSteps;
    self.continueButton.alpha = self.continueButton.enabled ? 1.0 : 0.4;
}

#pragma mark - 交互（空函数占位）

- (void)buildOptions { /* 子类实现 */ }
- (void)didTapContinue:(id)sender {
    Class next = [self nextViewControllerClass];
    if (next) {
        OnboardingBaseViewController *vc = [[next alloc] init];
        [self.navigationController pushViewController:vc animated:YES];
    } else {
        // 结束：无下一步，说明是最后一个引导页
        // TODO: connect business action — 进入主 App
    }
}
- (void)didTapBack:(id)sender { [self.navigationController popViewControllerAnimated:YES]; }
- (void)didTapSkip:(id)sender {
    // 跳过：直接进入引导完成页
    OnboardingDoneViewController *done = [[OnboardingDoneViewController alloc] init];
    [self.navigationController pushViewController:done animated:YES];
}

@end
