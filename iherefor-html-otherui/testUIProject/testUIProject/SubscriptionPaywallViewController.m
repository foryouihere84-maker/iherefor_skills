//
//  SubscriptionPaywallViewController.m
//  testUIProject
//
//  订阅付费墙（无免费试用）页面。
//
//  ── 先定路线：本页**只有一份手机稿** ─────────────────────────────────────
//  项目的设计列表里订阅只有 `订阅-无免费试用`（196.5×426 @2x = 393×852），
//  **没有 `订阅-无免费试用-iPad`**。按 skill `adaptive-layout.md §0.5`，
//  「只有 `xx`（无 iPad 稿）」这一档走**宽度轴**，而不是按设备分两套尺寸。
//
//  旧代码这里有一条 `isPad` 分支，把另一张页面 `10.2" iPad备份 6` 当成 iPad 稿：
//  1) 它不在本项目的 24 张设计稿里；2) 它是**免费试用版**（卡片文案是
//  「Free trial enabled / Expires today / 3 days free」），而本页是**无免费试用版**
//  （「Weekly $7.99/week / Yearly $49.99/year」）——**内容结构都不同**，
//  尺寸无从移植；3) 连品牌名都不同（那张写 "Color me"，本页写 "Pop Color Art"）。
//  所以 `heroHeightForTrait` 的 412、`cardHeight` 的 78、`ctaHeight` 的 84、
//  内容列 480、以及 141 / 64 / 43 / 28 / 12 这些间距全部删掉 ——
//  它们量的是别的页面的别的控件。
//
//  ── 布局契约（闭合方式一览）─────────────────────────────────────────────
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | hero | 宽 `pinned` 贴页面两侧（full-bleed）；高 `fixed` 321（**设计常量**，见下） | 顶贴页面顶 `pinned` |
//  | hero 图 | `pinned` 铺满 hero 框（`ScaleAspectFill`，宽画布是裁切不是拉伸） | — |
//  | 关闭键 | `fixed` 32×32（图标点值是视觉常量） | 贴安全区 左 10 / 上 8（`pinned`） |
//  | 内容列 | 宽 **`bounded` 封顶 480** + `<=` 页面宽−46；偏好值 `==` 页面宽−46 @999 | 水平 `centered`；纵向贴 hero 底 `pinned` +3 |
//  | 标题 | `intrinsic`（行高 29 走段落样式） | 贴内容列顶 `pinned` +1（稿件行的 marginTop） |
//  | paint 图标 | `fixed` 32×32 | 贴标题尾 `pinned` +4；与标题 `centered` |
//  | 副标题 | `intrinsic`（行高 18 走段落样式） | 贴标题底 `pinned` +11 |
//  | 价格卡 | 宽 `pinned` 贴内容列；高 `>=` 68（动态字体下可长高不裁字） | 堆叠：副标题 +33、卡间距 +24 |
//  | Best Value | `fixed` 100×28（标签点值尺寸） | 贴年卡 右上（`pinned` −24 / −14） |
//  | CTA | 宽 `pinned` 贴内容列；高 `>=` 68；圆角=高度一半（胶囊，`layoutSubviews` 里算） | 贴年卡底 `pinned` +98 |
//  | 底部链接 | `intrinsic` | 贴 CTA 底 `pinned` +12；左 60 / 中 `centered` / 右 −55 |
//
//  ── 宽度轴（`max-content-width`）────────────────────────────────────────
//  内容列**封顶 480 并居中**，在窄窗口（iPad 分屏 ~320pt）上退化为「页面宽 − 46」。
//  480 是**判断值**不是抄来的数字：本页没有 iPad 稿，没有第二出处，
//  所以只能按「单列付费墙在宽屏上的可读上限」定，并写在 `PaywallStyle` 里备查。
//  绝不用 `equalToConstant` 固定宽度 —— 那会在分屏下直接溢出。
//
//  ── 已知待确认（不擅自决定，留给设计侧）────────────────────────────────
//  · 关闭键：稿件里它是「32×32 圆形底（fill #D8D8D8 + 2pt #979797 描边）+ ✕」，
//    而工程里的 `paywall_close_icon` 切图**只有 ✕**（32×32 画布，✕ 占中间 12×12），
//    没有圆形底。这里按稿件补了圆形底；但切图里的 ✕ 是接近白色的 #F8F8F8，
//    压在 #D8D8D8 圆上对比度很低，建议让设计侧重新导出一版。
//  · `paywall_hero_top_ipad`（810×412）在本页已无人引用 —— 它是「另一张页面」的切图，
//    保留在 Assets 里未删除，若要清理请先确认那页是否另有去处。
//

#import "SubscriptionPaywallViewController.h"
#import "PaywallStyle.h"

@interface SubscriptionPaywallViewController ()

// hero 顶部区
@property (nonatomic, strong) UIView *heroView;
@property (nonatomic, strong) UIImageView *heroTopImage;
@property (nonatomic, strong) UIView *closeButton;   // 圆形底 + ✕ 图标
@property (nonatomic, strong) UIImageView *closeIcon;

// 内容列（第一层子视图；宽度由宽度轴闭合，纵向贴 hero 底）
@property (nonatomic, strong) UIView *contentColumn;
/// 内容列的「偏好满宽」约束：`width == 页面宽 − 2×内边距`，优先级 999。
/// 宽窗口上它会被 `<= maxContentWidth` 顶掉，于是列宽收敛到 480 并居中。
@property (nonatomic, strong) NSLayoutConstraint *contentPreferredWidthConstraint;

// 标题区
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UILabel *subtitleLabel;
@property (nonatomic, strong) UIImageView *paintIcon;

// 价格卡
@property (nonatomic, strong) UIView *weeklyCard;
@property (nonatomic, strong) UIView *yearlyCard;
@property (nonatomic, strong) UIView *bestValueBadge;

// CTA 与底部链接
@property (nonatomic, strong) UIButton *continueButton;
@property (nonatomic, strong) UIButton *privacyButton;
@property (nonatomic, strong) UIButton *termsButton;
@property (nonatomic, strong) UIButton *restoreButton;

@end

@implementation SubscriptionPaywallViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [PaywallStyle pageBackground];

    // 付费墙背景延伸到系统栏/灵动岛下方，前景内容用显式 inset。见 runtimeRisks.systemBars。
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    [self buildHero];
    [self buildContentColumn];
    [self buildFooter];

    // 旧代码在这里挂了一个 `UIApplicationDidChangeStatusBarOrientationNotification` 观察者，
    // 选择器写成 `@selector(traitCollectionDidChange)`（**没有冒号**）—— 它既不是
    // `traitCollectionDidChange:` 这个真实的重写（下面有），也会让通知中心把
    // 一个 NSNotification 当成 UITraitCollection 传进来。而且那个通知在 iOS 13 已废弃。
    // 现在宽度轴由约束本身表达（`<=` 上限 + 999 偏好值），窗口变宽变窄都由 Auto Layout
    // 连续求解，不再需要方向通知，整块观察者与 `dealloc` 一并删除。
}

- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    // 富文本不吃 `adjustsFontForContentSizeCategory`（那只作用于 `font`），
    // 字号档变了要把几段 attributed string 重建一次。
    BOOL sizeCategoryChanged =
        previousTraitCollection &&
        previousTraitCollection.preferredContentSizeCategory != self.traitCollection.preferredContentSizeCategory;
    if (sizeCategoryChanged) {
        [self applyTextStyles];
    }
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    // 胶囊是「高度的一半」，不是一个固定常量 —— CTA 高度是 `>=`（动态字体下会长高），
    // 写死 34 在高字号档就不再是胶囊了。设计尺寸 34 对应稿件的 68 高，
    // `PaywallStyle.ctaCornerRadius` 保留为该设计值的出处。
    self.continueButton.layer.cornerRadius = CGRectGetHeight(self.continueButton.bounds) / 2.0;
    self.closeButton.layer.cornerRadius = CGRectGetHeight(self.closeButton.bounds) / 2.0;
}

#pragma mark - Hero 顶部

- (void)buildHero {
    self.heroView = [[UIView alloc] init];
    self.heroView.translatesAutoresizingMaskIntoConstraints = NO;
    self.heroView.clipsToBounds = YES;
    // 稿件 hero 底层是一块 `rgba(241,240,242,1)` 的蒙版，就是页面底色 ——
    // 补上它，图片在宽画布上按 `ScaleAspectFill` 裁切时露出的部分才不是突兀的白。
    self.heroView.backgroundColor = [PaywallStyle pageBackground];
    [self.view addSubview:self.heroView];

    // 顶部整幅切图。高度是**设计常量**（321）：工程里两张 hero 切图的宽高比互不相同
    // （393×321 = 0.817 与 810×412 = 0.509），说明设计侧并不按宽度推高度；
    // 本页又没有 iPad 稿作为第二出处，所以它只能固定。
    self.heroTopImage = [[UIImageView alloc] initWithImage:[UIImage imageNamed:@"paywall_hero_top"]];
    self.heroTopImage.contentMode = UIViewContentModeScaleAspectFill;
    self.heroTopImage.translatesAutoresizingMaskIntoConstraints = NO;
    self.heroTopImage.userInteractionEnabled = NO;
    [self.heroView addSubview:self.heroTopImage];

    // 关闭键：稿件是「32×32 圆形底 + ✕」两件套，切图只含 ✕，所以要自己补圆形底。
    self.closeButton = [[UIView alloc] init];
    self.closeButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.closeButton.backgroundColor = [PaywallStyle closeButtonFill];
    self.closeButton.layer.borderWidth = [PaywallStyle closeButtonBorderWidth];
    self.closeButton.layer.borderColor = [PaywallStyle closeButtonBorder].CGColor;
    self.closeButton.userInteractionEnabled = YES;
    [self.closeButton addGestureRecognizer:
        [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapClose:)]];
    self.closeButton.accessibilityIdentifier = @"subscription_close";
    self.closeButton.isAccessibilityElement = YES;
    self.closeButton.accessibilityTraits = UIAccessibilityTraitButton;
    self.closeButton.accessibilityLabel = @"Close";
    [self.view addSubview:self.closeButton];

    self.closeIcon = [[UIImageView alloc] initWithImage:[UIImage imageNamed:@"paywall_close_icon"]];
    self.closeIcon.contentMode = UIViewContentModeCenter;
    self.closeIcon.userInteractionEnabled = NO;
    self.closeIcon.translatesAutoresizingMaskIntoConstraints = NO;
    [self.closeButton addSubview:self.closeIcon];

    [NSLayoutConstraint activateConstraints:@[
        // hero：宽 full-bleed（贴页面两侧），高是设计常量。
        [self.heroView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [self.heroView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.heroView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.heroView.heightAnchor constraintEqualToConstant:[PaywallStyle heroHeight]],

        [self.heroTopImage.topAnchor constraintEqualToAnchor:self.heroView.topAnchor],
        [self.heroTopImage.leadingAnchor constraintEqualToAnchor:self.heroView.leadingAnchor],
        [self.heroTopImage.trailingAnchor constraintEqualToAnchor:self.heroView.trailingAnchor],
        [self.heroTopImage.bottomAnchor constraintEqualToAnchor:self.heroView.bottomAnchor],

        // 关闭键：稿件 (10,52) 32×32 —— 相对安全区是 左 10 / 上 8（44pt 状态栏 + 8 = 52）。
        // 与向导页顶部栏同一个口径：取「离安全区顶 8」这一个设计常量，
        // 不按机型去补偿状态栏高度（见 OnboardingStyle.topBarTopInset 的说明）。
        [self.closeButton.leadingAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.leadingAnchor constant:10.0],
        [self.closeButton.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor constant:8.0],
        [self.closeButton.widthAnchor constraintEqualToConstant:32.0],
        [self.closeButton.heightAnchor constraintEqualToConstant:32.0],

        // ✕ 铺满圆底：切图是 32×32 画布、✕ 居中占 12×12，所以正好是稿件的比例。
        [self.closeIcon.topAnchor constraintEqualToAnchor:self.closeButton.topAnchor],
        [self.closeIcon.leadingAnchor constraintEqualToAnchor:self.closeButton.leadingAnchor],
        [self.closeIcon.trailingAnchor constraintEqualToAnchor:self.closeButton.trailingAnchor],
        [self.closeIcon.bottomAnchor constraintEqualToAnchor:self.closeButton.bottomAnchor],
    ]];
}

#pragma mark - 内容列

- (void)buildContentColumn {
    self.contentColumn = [[UIView alloc] init];
    self.contentColumn.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:self.contentColumn];

    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.numberOfLines = 0;
    self.titleLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.titleLabel.accessibilityIdentifier = @"subscription_title";
    [self.contentColumn addSubview:self.titleLabel];

    // paint 图标 (231,324) 32×32 —— 图标点值是**视觉常量**，用 `fixed`。
    self.paintIcon = [[UIImageView alloc] initWithImage:[UIImage imageNamed:@"paywall_paint_icon"]];
    self.paintIcon.contentMode = UIViewContentModeScaleAspectFit;
    self.paintIcon.translatesAutoresizingMaskIntoConstraints = NO;
    [self.contentColumn addSubview:self.paintIcon];

    self.subtitleLabel = [[UILabel alloc] init];
    self.subtitleLabel.numberOfLines = 0;
    self.subtitleLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.subtitleLabel.accessibilityIdentifier = @"subscription_subtitle";
    [self.contentColumn addSubview:self.subtitleLabel];

    // ── 宽度轴：`max-content-width` ──
    // 三条一起才成立：`<=` 封顶（设计上限）、`<=` 页面宽−2×内边距（窄窗口的下限保障）、
    // 以及一条低优先级的「偏好满宽」—— 没有它，光靠两个 `<=` 列宽是不确定的。
    // 优先级用 `UILayoutPriorityDefaultHigh`（750）而不是 999：这是本工程里
    // `OnboardingBaseViewController` 已经确定的同一条惯例（「偏好值」= 750，让位给必满足的 `<=`），
    // 全工程一套写法比多一个孤立的 999 更好复核。
    self.contentPreferredWidthConstraint =
        [self.contentColumn.widthAnchor constraintEqualToAnchor:self.view.widthAnchor
                                                      constant:-2.0 * [PaywallStyle contentHorizontalInset]];
    self.contentPreferredWidthConstraint.priority = UILayoutPriorityDefaultHigh;

    [NSLayoutConstraint activateConstraints:@[
        // 纵向：贴 hero 底 `pinned` +3（稿件内容列 paddingTop 3），与宽度档无关。
        [self.contentColumn.topAnchor constraintEqualToAnchor:self.heroView.bottomAnchor constant:3.0],
        // 水平：`centered` —— 窄窗口下柱宽就等于可用宽，宽窗口下 480 居中。
        [self.contentColumn.centerXAnchor constraintEqualToAnchor:self.view.centerXAnchor],
        [self.contentColumn.widthAnchor constraintLessThanOrEqualToConstant:[PaywallStyle maxContentWidth]],
        [self.contentColumn.widthAnchor constraintLessThanOrEqualToAnchor:self.view.widthAnchor
                                                                constant:-2.0 * [PaywallStyle contentHorizontalInset]],
        self.contentPreferredWidthConstraint,

        // 标题：贴内容列顶 `pinned` +1（稿件里标题行有 marginTop 1）。
        // 高度走段落样式 → `intrinsic`，不再钉 `equalToConstant 29`：
        // 钉高度等于把「文本框高」当视觉常量，字号档一放大会把字切掉。
        [self.titleLabel.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor],
        [self.titleLabel.topAnchor constraintEqualToAnchor:self.contentColumn.topAnchor constant:1.0],

        // paint 图标：贴标题尾 +4，并与标题 `centered`（稿件图标框 324..356 的中心
        // 与标题框 325..354 的中心只差 0.5pt，属于同一行的居中，不是底部对齐）。
        [self.paintIcon.leadingAnchor constraintEqualToAnchor:self.titleLabel.trailingAnchor constant:4.0],
        [self.paintIcon.centerYAnchor constraintEqualToAnchor:self.titleLabel.centerYAnchor],
        [self.paintIcon.widthAnchor constraintEqualToConstant:32.0],
        [self.paintIcon.heightAnchor constraintEqualToConstant:32.0],
        // 图标不许被标题挤出去：标题先收缩。
        [self.paintIcon.trailingAnchor constraintLessThanOrEqualToAnchor:self.contentColumn.trailingAnchor],

        // 副标题：贴标题底 `pinned` +11，两侧贴内容列。
        // 稿件副标题框是 (26,365,323,54) —— 宽 323、右留 21，属手工摆放的文本框，
        // 这里按内容列整宽表达（同一段文案的换行点一致），与稿件 3pt 级偏差同类处理。
        [self.subtitleLabel.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor],
        [self.subtitleLabel.trailingAnchor constraintEqualToAnchor:self.contentColumn.trailingAnchor],
        [self.subtitleLabel.topAnchor constraintEqualToAnchor:self.titleLabel.bottomAnchor constant:11.0],
    ]];

    [self applyTextStyles];
    [self buildCards];
    [self buildCTA];
}

/// 把标题 / 副标题的样式装上去。行高走段落样式，所以字号档变化时重建即可。
- (void)applyTextStyles {
    self.titleLabel.attributedText =
        [self attributedText:@"Choose Your Plan"
                        font:[PaywallStyle titleFont]
                       color:[PaywallStyle titleColor]
                  lineHeight:[PaywallStyle titleLineHeight]
                       alpha:1.0];

    self.subtitleLabel.attributedText =
        [self attributedText:@"Unlock all Pop Color Art features and enjoy an ad-free experience."
                        font:[PaywallStyle subtitleFont]
                       color:[PaywallStyle titleColor]
                  lineHeight:[PaywallStyle subtitleLineHeight]
                       alpha:1.0];
}

/// 统一的富文本构造：字号按文本样式缩放，行高按设计值上下夹紧。
-(NSAttributedString *)attributedText:(NSString *)text
                                 font:(UIFont *)font
                                color:(UIColor *)color
                           lineHeight:(CGFloat)lineHeight
                                alpha:(CGFloat)alpha {
    NSMutableParagraphStyle *para = [[NSMutableParagraphStyle alloc] init];
    para.minimumLineHeight = lineHeight;
    para.maximumLineHeight = lineHeight;
    para.alignment = NSTextAlignmentLeft;

    NSMutableDictionary *attrs = [NSMutableDictionary dictionary];
    attrs[NSFontAttributeName] = [[UIFontMetrics metricsForTextStyle:UIFontTextStyleBody] scaledFontForFont:font];
    attrs[NSForegroundColorAttributeName] = [color colorWithAlphaComponent:alpha];
    attrs[NSParagraphStyleAttributeName] = para;
    return [[NSAttributedString alloc] initWithString:(text ?: @"") attributes:attrs];
}

#pragma mark - 价格卡

- (void)buildCards {
    // Weekly 卡（选中态：深描边 #141414，白底）
    self.weeklyCard = [self makeCardSelected:YES];
    [self.contentColumn addSubview:self.weeklyCard];

    UILabel *weeklyTitle = [self makeCardTitle:@"Weekly"];
    [self.weeklyCard addSubview:weeklyTitle];

    UILabel *weeklyPrice = [self makeCardPrice:@"$7.99/week"];
    [self.weeklyCard addSubview:weeklyPrice];

    // Yearly 卡（未选中：浅灰描边 #D7D7D7，白底）
    self.yearlyCard = [self makeCardSelected:NO];
    [self.contentColumn addSubview:self.yearlyCard];

    UILabel *yearlyTitle = [self makeCardTitle:@"Yearly"];
    [self.yearlyCard addSubview:yearlyTitle];

    UILabel *yearlyPrice = [self makeCardPrice:@"$49.99/year"];
    [self.yearlyCard addSubview:yearlyPrice];

    UILabel *yearlyHint = [self makeCardPrice:@"Then $0.95/week"];
    [self.yearlyCard addSubview:yearlyHint];

    // 「Best Value」标签：蓝紫底 100×28，圆角 6 —— 标签点值尺寸是视觉常量。
    self.bestValueBadge = [[UIView alloc] init];
    self.bestValueBadge.backgroundColor = [PaywallStyle accent];
    self.bestValueBadge.layer.cornerRadius = [PaywallStyle badgeCornerRadius];
    self.bestValueBadge.layer.masksToBounds = YES;
    self.bestValueBadge.translatesAutoresizingMaskIntoConstraints = NO;
    [self.yearlyCard addSubview:self.bestValueBadge];

    UILabel *badgeLabel = [[UILabel alloc] init];
    badgeLabel.text = @"Best Value";
    // 稿件实测：「Best Value」是 **Avenir-Heavy 10pt**（与卡片标题同字重、与价格同字号），
    // 旧代码用 cardBodyFont（Avenir-Medium），字重错了。
    badgeLabel.font = [PaywallStyle badgeFont];
    badgeLabel.textColor = [UIColor whiteColor];
    badgeLabel.textAlignment = NSTextAlignmentRight;
    badgeLabel.translatesAutoresizingMaskIntoConstraints = NO;
    [self.bestValueBadge addSubview:badgeLabel];

    [NSLayoutConstraint activateConstraints:@[
        // ── Weekly ──
        [self.weeklyCard.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor],
        [self.weeklyCard.trailingAnchor constraintEqualToAnchor:self.contentColumn.trailingAnchor],
        // 副标题 → Weekly 卡：33 = 稿件间距 15 + 副标题文本框内的剩余 18。
        // 稿件副标题框被钉成 54 高（三行位）而文案只占两行（36），所以视觉间距是 15 + 18。
        // 这里让文本框按内容闭口（`intrinsic`，36），把 18 并进间距 —— 像素一致，
        // 而且文案变长 / 字号档放大时是往下推，不是把字压在卡片底下。
        [self.weeklyCard.topAnchor constraintEqualToAnchor:self.subtitleLabel.bottomAnchor constant:33.0],
        // 高度 `>=`：68 是设计下限，动态字体放大时卡片可以长高而不是裁字。
        [self.weeklyCard.heightAnchor constraintGreaterThanOrEqualToConstant:[PaywallStyle cardHeight]],

        [weeklyTitle.leadingAnchor constraintEqualToAnchor:self.weeklyCard.leadingAnchor constant:16.0],
        [weeklyTitle.topAnchor constraintEqualToAnchor:self.weeklyCard.topAnchor constant:24.0],

        [weeklyPrice.trailingAnchor constraintEqualToAnchor:self.weeklyCard.trailingAnchor constant:-16.0],
        // 稿件价格框 (301,461,53,14) 底 475，卡底 502 → 内边距 **27**（旧代码写 23，差 4pt）。
        [weeklyPrice.bottomAnchor constraintEqualToAnchor:self.weeklyCard.bottomAnchor constant:-27.0],

        // ── Yearly ──
        [self.yearlyCard.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor],
        [self.yearlyCard.trailingAnchor constraintEqualToAnchor:self.contentColumn.trailingAnchor],
        [self.yearlyCard.topAnchor constraintEqualToAnchor:self.weeklyCard.bottomAnchor constant:24.0],
        [self.yearlyCard.heightAnchor constraintGreaterThanOrEqualToConstant:[PaywallStyle cardHeight]],

        [yearlyTitle.leadingAnchor constraintEqualToAnchor:self.yearlyCard.leadingAnchor constant:16.0],
        [yearlyTitle.topAnchor constraintEqualToAnchor:self.yearlyCard.topAnchor constant:16.0],

        [yearlyPrice.leadingAnchor constraintEqualToAnchor:self.yearlyCard.leadingAnchor constant:16.0],
        [yearlyPrice.topAnchor constraintEqualToAnchor:yearlyTitle.bottomAnchor constant:1.0],

        [yearlyHint.trailingAnchor constraintEqualToAnchor:self.yearlyCard.trailingAnchor constant:-16.0],
        // 稿件提示框 (275,553,79,14) 中心 560，正好是卡片中心（526 + 68/2）→ **卡片内垂直居中**。
        // 旧代码钉的是「距卡底 15」（旧口径下卡高 68 时落在 579），比稿件的 567 低 12pt。
        [yearlyHint.centerYAnchor constraintEqualToAnchor:self.yearlyCard.centerYAnchor],

        // ── Best Value 标签 ──
        // 稿件标签框 (246,512,100,28)：右缘 346，年卡右缘 370 → 24；顶 512，年卡顶 526 → 上探 14。
        [self.bestValueBadge.trailingAnchor constraintEqualToAnchor:self.yearlyCard.trailingAnchor constant:-24.0],
        [self.bestValueBadge.topAnchor constraintEqualToAnchor:self.yearlyCard.topAnchor constant:-14.0],
        [self.bestValueBadge.widthAnchor constraintEqualToConstant:100.0],
        [self.bestValueBadge.heightAnchor constraintEqualToConstant:28.0],

        // 稿件文字框 (271,520,50,14) 右缘 321，标签右缘 346 → 25（标签 paddingRight 25）。
        [badgeLabel.trailingAnchor constraintEqualToAnchor:self.bestValueBadge.trailingAnchor constant:-25.0],
        [badgeLabel.centerYAnchor constraintEqualToAnchor:self.bestValueBadge.centerYAnchor],
    ]];
}

- (UIView *)makeCardSelected:(BOOL)selected {
    UIView *card = [[UIView alloc] init];
    card.backgroundColor = [UIColor whiteColor];
    card.layer.cornerRadius = [PaywallStyle cardCornerRadius];
    card.layer.borderWidth = [PaywallStyle cardBorderWidth];
    card.layer.borderColor = (selected ? [PaywallStyle cardBorderSelected] : [PaywallStyle cardBorderMuted]).CGColor;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;
    return card;
}

- (UILabel *)makeCardTitle:(NSString *)text {
    UILabel *l = [[UILabel alloc] init];
    l.attributedText = [self attributedText:text
                                       font:[PaywallStyle cardTitleFont]
                                      color:[PaywallStyle cardInk]
                                 lineHeight:[PaywallStyle cardTitleLineHeight]
                                      alpha:1.0];
    l.numberOfLines = 1;
    l.translatesAutoresizingMaskIntoConstraints = NO;
    return l;
}

- (UILabel *)makeCardPrice:(NSString *)text {
    UILabel *l = [[UILabel alloc] init];
    // 稿件三处价格节点 `opacity = 60` —— 不透明度是设计常量，取 token 而不是裸写 0.6。
    l.attributedText = [self attributedText:text
                                       font:[PaywallStyle cardBodyFont]
                                      color:[PaywallStyle cardInk]
                                 lineHeight:[PaywallStyle cardBodyLineHeight]
                                      alpha:[PaywallStyle cardBodyAlpha]];
    l.numberOfLines = 1;
    l.translatesAutoresizingMaskIntoConstraints = NO;
    return l;
}

#pragma mark - CTA

- (void)buildCTA {
    self.continueButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.continueButton.backgroundColor = [PaywallStyle accent];
    // 胶囊圆角是「高度的一半」，在 `viewDidLayoutSubviews` 里按实际高度算（见那里的说明）。
    self.continueButton.layer.masksToBounds = YES;
    // 文案只有一份手机稿（"Continue"）。旧代码这里按 `isPad` 换成 "Try For Free" ——
    // 那句来自另一张免费试用页，与本页不是同一份稿。
    [self.continueButton setTitle:@"Continue" forState:UIControlStateNormal];
    [self.continueButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    self.continueButton.titleLabel.font = [PaywallStyle ctaFont];
    self.continueButton.titleLabel.adjustsFontForContentSizeCategory = YES;
    [self.continueButton addTarget:self action:@selector(didTapContinue:) forControlEvents:UIControlEventTouchUpInside];
    self.continueButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.continueButton.accessibilityIdentifier = @"subscription_continue";
    [self.contentColumn addSubview:self.continueButton];

    [NSLayoutConstraint activateConstraints:@[
        [self.continueButton.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor],
        [self.continueButton.trailingAnchor constraintEqualToAnchor:self.contentColumn.trailingAnchor],
        // 年卡 → CTA：稿件 98（年卡底 594、CTA 顶 692）。
        [self.continueButton.topAnchor constraintEqualToAnchor:self.yearlyCard.bottomAnchor constant:98.0],
        // 高度 `>=`：68 是设计下限（胶囊半径 34 = 68 ÷ 2）。
        [self.continueButton.heightAnchor constraintGreaterThanOrEqualToConstant:[PaywallStyle ctaHeight]],
    ]];
}

#pragma mark - 底部链接

- (void)buildFooter {
    // 文案只有一份手机稿：Privacy / Terms / Restore。
    // 旧代码在 iPad 分支里换成 "Privacy Policy" / "Terms of service" 并去掉 Restore ——
    // 同样来自那张免费试用页（它的底部只有两条链接），不是本页的 iPad 稿。
    self.privacyButton = [self makeFooterLink:@"Privacy" sel:@selector(didTapPrivacy:)];
    self.termsButton    = [self makeFooterLink:@"Terms"   sel:@selector(didTapTerms:)];
    self.restoreButton  = [self makeFooterLink:@"Restore" sel:@selector(didTapRestore:)];
    [self.contentColumn addSubview:self.privacyButton];
    [self.contentColumn addSubview:self.termsButton];
    [self.contentColumn addSubview:self.restoreButton];

    // 三条链接在稿件里是**手工摆放**的（左 83 / 中 197 / 右 315，两侧留白 60 / 55 并不相等），
    // 不是等分布；高度交给 `intrinsic`（按钮自带行高），不再钉 `equalToConstant 16` ——
    // 钉的是文本行高本身，属于把文本框高当视觉常量。
    [NSLayoutConstraint activateConstraints:@[
        [self.privacyButton.topAnchor constraintEqualToAnchor:self.continueButton.bottomAnchor constant:12.0],
        [self.privacyButton.leadingAnchor constraintEqualToAnchor:self.contentColumn.leadingAnchor constant:60.0],

        [self.termsButton.topAnchor constraintEqualToAnchor:self.continueButton.bottomAnchor constant:12.0],
        [self.termsButton.centerXAnchor constraintEqualToAnchor:self.contentColumn.centerXAnchor],

        [self.restoreButton.topAnchor constraintEqualToAnchor:self.continueButton.bottomAnchor constant:12.0],
        [self.restoreButton.trailingAnchor constraintEqualToAnchor:self.contentColumn.trailingAnchor constant:-55.0],
    ]];
}

- (UIButton *)makeFooterLink:(NSString *)text sel:(SEL)sel {
    UIButton *b = [UIButton buttonWithType:UIButtonTypeCustom];
    [b setTitle:text forState:UIControlStateNormal];
    [b setTitleColor:[PaywallStyle footerLink] forState:UIControlStateNormal];
    b.titleLabel.font = [PaywallStyle footerFont];
    b.titleLabel.adjustsFontForContentSizeCategory = YES;
    [b addTarget:self action:sel forControlEvents:UIControlEventTouchUpInside];
    b.translatesAutoresizingMaskIntoConstraints = NO;
    return b;
}

#pragma mark - 点击事件（业务未实现，占位）

- (void)didTapClose:(id)sender    { /* TODO: connect business action — 关闭付费墙 */ }
- (void)didTapContinue:(id)sender { /* TODO: connect business action — 继续订阅 */ }
- (void)didTapPrivacy:(id)sender  { /* TODO: connect business action — 隐私条款 */ }
- (void)didTapTerms:(id)sender    { /* TODO: connect business action — 服务条款 */ }
- (void)didTapRestore:(id)sender  { /* TODO: connect business action — 恢复购买 */ }

@end
