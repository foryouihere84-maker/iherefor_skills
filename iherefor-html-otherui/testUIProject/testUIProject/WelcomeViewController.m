//
//  WelcomeViewController.m
//  testUIProject
//
//  欢迎页。
//
//  布局契约（闭合方式一览）：
//
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | 背景 | `pinned` 四边贴页面（full-bleed，不自己声明宽高） | — |
//  | 文字组 | 宽 `equal`（= 标题文字宽，稿件 339/436 与标题盒精确相等）；高由两个子视图闭口 | 水平 `centered`（两稿正中，比值 0.5）；纵向 **`proportional`**：centerY = 页面高 × 0.417840 / 0.392130 |
//  | 标题 | `intrinsic`（文字撑开，行高走段落样式 34/43）；另加 `bounded` 上限 | 顶贴组顶 `pinned` |
//  | 副标题 | `intrinsic`（行高走段落样式 26/36）；另加 `bounded` 上限 | 贴标题底 `pinned` 12 / 14；组内 `centered`；底贴组底 |
//
//  双稿是两套并列独立参考：欢迎语（393×852），启屏欢迎语-iPad（810×1080）。
//  文案一致，字号 / 行高 / 间距 / 字距跨稿分档，非等比放大 —— 见 `usesTabletDesignValues`。
//
//  宽度轴：背景 full-bleed；文字组是 `centered` + `intrinsic`，天然不随平板拉宽，
//  不需要另立宽度档。
//
//  归属说明：背景与启屏是**同一张装饰图**，所以复用 `splash_background*` 资源名。
//  这是有意的共用，不是「splash 专属资源被误用」——两个页面同属品牌前置段。
//

#import "WelcomeViewController.h"
#import "WelcomeStyle.h"
#import "OnboardingStyle.h"
#import "PurposeOnboardingViewController.h"

@interface WelcomeViewController ()

@property (nonatomic, strong) UIImageView *backgroundView;
@property (nonatomic, strong) UIView *textGroup;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UILabel *subtitleLabel;

// 文字组纵向位置约束（按页面高度比例闭合，比例跨稿分档）
@property (nonatomic, strong, nullable) NSLayoutConstraint *textGroupCenterYConstraint;
// 已经装上去的比例，用来判断要不要换约束
@property (nonatomic, assign) CGFloat appliedCenterYRatio;

// 标题→副标题间距约束（双稿分档）
@property (nonatomic, strong) NSLayoutConstraint *titleToSubtitleGapConstraint;

@end

@implementation WelcomeViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor whiteColor];

    // 背景 underlap 状态栏；文字组按页面高度比例定位，也需要整页铺开来对画布的 852 / 1080。
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    [self buildBackground];
    [self buildTextGroup];
    [self applyTraits];

    // 欢迎页设计稿无按钮，点击任意处进入引导流程（与启动页一致）。
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapWelcome:)];
    [self.view addGestureRecognizer:tap];
}

- (void)didTapWelcome:(id)sender {
    // TODO: connect business action — 进入引导流程第一步
    PurposeOnboardingViewController *purpose = [[PurposeOnboardingViewController alloc] init];
    [self.navigationController pushViewController:purpose animated:YES];
}

- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];
    [self applyTraits];
}

- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    // 选稿（两套参考）与字号档变化时同步刷新。
    [self applyTraits];
}

#pragma mark - 选稿分档（双稿 sizeVariants）

/// 当前该用哪一稿的样式常量。
///
/// 这是**选稿**，不是布局决策：欢迎语 / 启屏欢迎语-iPad 是两套并列独立参考，
/// 不存在派生关系，所以按平台挑一稿的字号 / 行高 / 间距 / 字距。
/// 返回值只喂给样式常量，**绝不参与任何约束取值** ——
/// 用设备类型决定「布局怎么收口」才是违规（那叫设备分支，不叫宽度轴）。
- (BOOL)usesTabletDesignValues {
    return self.traitCollection.userInterfaceIdiom == UIUserInterfaceIdiomPad;
}

- (CGFloat)titleFontSize    { return self.usesTabletDesignValues ? [WelcomeStyle titleFontSizeIpad]    : [WelcomeStyle titleFontSizePhone]; }
- (CGFloat)subtitleFontSize { return self.usesTabletDesignValues ? [WelcomeStyle subtitleFontSizeIpad] : [WelcomeStyle subtitleFontSizePhone]; }
- (CGFloat)titleLineHeight    { return self.usesTabletDesignValues ? [WelcomeStyle titleLineHeightIpad]    : [WelcomeStyle titleLineHeightPhone]; }
- (CGFloat)subtitleLineHeight { return self.usesTabletDesignValues ? [WelcomeStyle subtitleLineHeightIpad] : [WelcomeStyle subtitleLineHeightPhone]; }
- (CGFloat)titleToSubtitleGap { return self.usesTabletDesignValues ? [WelcomeStyle titleToSubtitleGapIpad] : [WelcomeStyle titleToSubtitleGapPhone]; }
- (CGFloat)titleLetterSpacing { return self.usesTabletDesignValues ? [WelcomeStyle titleLetterSpacingIpad] : [WelcomeStyle titleLetterSpacingPhone]; }

- (UIImage *)backgroundImage {
    NSString *name = self.usesTabletDesignValues ? @"splash_background_ipad" : @"splash_background";
    return [UIImage imageNamed:name];
}

- (void)applyTraits {
    self.backgroundView.image = [self backgroundImage];

    self.titleLabel.attributedText = [self titleAttributedText];
    self.subtitleLabel.attributedText = [self subtitleAttributedText];

    if (self.titleToSubtitleGapConstraint) {
        self.titleToSubtitleGapConstraint.constant = [self titleToSubtitleGap];
    }

    [self applyTextGroupCenterY];
}

#pragma mark - 文字组纵向位置（页面高度比例）

/// 装文字组的纵向闭口：`centerY = 页面高 × ratio`。
///
/// 这是 §3.1.1 对**第一层子视图**的要求 —— 纵向位置始终按页面高度比例闭合，
/// 不跟着宽度档走，也不是「居中再挪一个常量」。
///
/// 两个实现约束：`multiplier` 是只读的，比例一变只能**换一条约束**；
/// 而纵向锚点没有 `constraintEqualToAnchor:multiplier:` 变体
/// （它只存在于 `NSLayoutDimension`），所以要落到 `constraintWithItem:` 上。
- (void)applyTextGroupCenterY {
    CGFloat ratio = self.usesTabletDesignValues ? [WelcomeStyle textGroupCenterYRatioIpad]
                                                : [WelcomeStyle textGroupCenterYRatioPhone];

    if (self.textGroupCenterYConstraint && fabs(self.appliedCenterYRatio - ratio) < 1e-9) {
        return;   // 比例没变，还是同一条
    }
    if (self.textGroupCenterYConstraint) {
        self.textGroupCenterYConstraint.active = NO;
    }

    // `textGroup` 是 `self.view` 的直接子视图，共同坐标系就是 `self.view` 自身，
    // 而一个视图在它自己的坐标系里 `bottom` 的值就是它的 `height` ——
    // 于是 `centerY = ratio × view.bottom` 即 `centerY = ratio × 页面高`。
    NSLayoutConstraint *constraint =
        [NSLayoutConstraint constraintWithItem:self.textGroup
                                    attribute:NSLayoutAttributeCenterY
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:self.view
                                    attribute:NSLayoutAttributeBottom
                                   multiplier:ratio
                                     constant:0.0];
    constraint.active = YES;
    self.textGroupCenterYConstraint = constraint;
    self.appliedCenterYRatio = ratio;
}

#pragma mark - 文本

/// 标题（黑体，负字距，行高走段落样式）。
///
/// 行高用 `minimumLineHeight` / `maximumLineHeight` 而不是给 label 加一条高度约束 ——
/// 加高度约束等于把「文字区高度」当成视觉常量，而 §2.2 的视觉常量是**行高**本身，
/// 不是盒子高度；走段落样式后 label 的固有高度自然就是 34 / 43，尺寸轴是 `intrinsic`。
- (NSAttributedString *)titleAttributedText {
    NSMutableParagraphStyle *para = [[NSMutableParagraphStyle alloc] init];
    para.alignment = NSTextAlignmentCenter;
    para.minimumLineHeight = [self titleLineHeight];
    para.maximumLineHeight = [self titleLineHeight];

    NSMutableDictionary *attrs = [NSMutableDictionary dictionary];
    attrs[NSFontAttributeName] = [self titleFont];
    attrs[NSForegroundColorAttributeName] = [WelcomeStyle textColor];
    attrs[NSParagraphStyleAttributeName] = para;
    attrs[NSKernAttributeName] = @([self titleLetterSpacing]);

    return [[NSAttributedString alloc] initWithString:@"Welcome to Pop Color Art" attributes:attrs];
}

/// 副标题（中体，行高走段落样式）。
/// 稿件副标题行高 26 / 36 比该字号的天然行高更紧，只有走段落样式才能压出设计的那一行，
/// 靠给 label 钉一条 26 的高度约束反而会把字切掉。
- (NSAttributedString *)subtitleAttributedText {
    NSMutableParagraphStyle *para = [[NSMutableParagraphStyle alloc] init];
    para.alignment = NSTextAlignmentCenter;
    para.minimumLineHeight = [self subtitleLineHeight];
    para.maximumLineHeight = [self subtitleLineHeight];

    NSMutableDictionary *attrs = [NSMutableDictionary dictionary];
    attrs[NSFontAttributeName] = [self subtitleFont];
    attrs[NSForegroundColorAttributeName] = [WelcomeStyle textColor];
    attrs[NSParagraphStyleAttributeName] = para;

    return [[NSAttributedString alloc] initWithString:@"Make every day colorful" attributes:attrs];
}

/// 标题字体：按字号档缩放，`adjustsFontForContentSizeCategory` 对富文本不生效，
/// 所以缩放必须在**造富文本之前**做（字号档变化时 `applyTraits` 会重建）。
- (UIFont *)titleFont {
    UIFont *base = [WelcomeStyle titleFontOfSize:[self titleFontSize]];
    return [OnboardingStyle scaledFont:base forTextStyle:UIFontTextStyleTitle1];
}

/// 副标题字体：同上。
- (UIFont *)subtitleFont {
    UIFont *base = [WelcomeStyle subtitleFontOfSize:[self subtitleFontSize]];
    return [OnboardingStyle scaledFont:base forTextStyle:UIFontTextStyleTitle3];
}

#pragma mark - 背景

- (void)buildBackground {
    self.backgroundView = [[UIImageView alloc] init];
    self.backgroundView.contentMode = UIViewContentModeScaleAspectFill;
    self.backgroundView.clipsToBounds = YES;
    self.backgroundView.userInteractionEnabled = NO;
    self.backgroundView.translatesAutoresizingMaskIntoConstraints = NO;
    self.backgroundView.accessibilityIdentifier = @"welcome_background";
    [self.view addSubview:self.backgroundView];

    // `pinned` 四边 —— 背景不声明自己的宽高。
    [NSLayoutConstraint activateConstraints:@[
        [self.backgroundView.topAnchor constraintEqualToAnchor:self.view.topAnchor],
        [self.backgroundView.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.backgroundView.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.backgroundView.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor],
    ]];
}

#pragma mark - 文字组

- (void)buildTextGroup {
    self.textGroup = [[UIView alloc] init];
    self.textGroup.translatesAutoresizingMaskIntoConstraints = NO;
    self.textGroup.userInteractionEnabled = NO;
    [self.view addSubview:self.textGroup];

    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.numberOfLines = 0;
    self.titleLabel.textAlignment = NSTextAlignmentCenter;
    self.titleLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.titleLabel.accessibilityIdentifier = @"welcome_title";
    [self.textGroup addSubview:self.titleLabel];

    self.subtitleLabel = [[UILabel alloc] init];
    self.subtitleLabel.numberOfLines = 0;
    self.subtitleLabel.textColor = [WelcomeStyle textColor];
    self.subtitleLabel.textAlignment = NSTextAlignmentCenter;
    self.subtitleLabel.translatesAutoresizingMaskIntoConstraints = NO;
    self.subtitleLabel.accessibilityIdentifier = @"welcome_subtitle";
    [self.textGroup addSubview:self.subtitleLabel];

    self.titleToSubtitleGapConstraint = [self.subtitleLabel.topAnchor constraintEqualToAnchor:self.titleLabel.bottomAnchor
                                                                                    constant:[self titleToSubtitleGap]];

    [NSLayoutConstraint activateConstraints:@[
        // 水平：两稿的组都是页面正中（稿件组 centerX 196.5/393、405/810，比值都是 0.5），
        // 所以是 `centered`。稿件里那 27 / 187 的「内边距」是这个居中的余量，
        // 不是内边距 —— 组宽 339/436 与标题盒宽精确相等。
        [self.textGroup.centerXAnchor constraintEqualToAnchor:self.view.centerXAnchor],

        // 组的宽度由**标题**闭口（`equal`）：标题盒宽 339（文字 28pt 黑体实测）
        // 与 436（36pt 黑体实测）都等于组宽，副标题更窄、在里面居中。
        [self.textGroup.widthAnchor constraintEqualToAnchor:self.titleLabel.widthAnchor],

        // 组的纵向闭口在 `applyTextGroupCenterY` 里按页面高度比例装（比例跨稿分档，会换约束）。

        // 标题：`intrinsic` 宽高（行高走段落样式），顶贴组顶。
        [self.titleLabel.topAnchor constraintEqualToAnchor:self.textGroup.topAnchor],
        [self.titleLabel.centerXAnchor constraintEqualToAnchor:self.textGroup.centerXAnchor],
        // `bounded`：字号档拉到很大时给个上限，避免文字宽于页面。有上限才会换行而不是溢出。
        [self.titleLabel.widthAnchor constraintLessThanOrEqualToAnchor:self.view.widthAnchor constant:-40.0],

        // 副标题：贴标题底（`pinned`，视觉常量 12 / 14），组内居中，底贴组底。
        // 这两条把组高也一并闭口了：手机 34+12+26 = 72、iPad 43+14+36 = 93（稿件实测同值）。
        self.titleToSubtitleGapConstraint,
        [self.subtitleLabel.centerXAnchor constraintEqualToAnchor:self.textGroup.centerXAnchor],
        [self.subtitleLabel.bottomAnchor constraintEqualToAnchor:self.textGroup.bottomAnchor],
        [self.subtitleLabel.widthAnchor constraintLessThanOrEqualToAnchor:self.view.widthAnchor constant:-40.0],
    ]];
}

@end
