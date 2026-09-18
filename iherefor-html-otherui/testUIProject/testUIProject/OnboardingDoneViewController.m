//
//  OnboardingDoneViewController.m
//
//  引导步骤 7：引导完成。无选项，直接显示完成态 + CTA。
//
//  **与向导各页的关键差别**：本页没有顶部栏（稿件里没有返回键 / 进度条 / Skip），
//  标题也不在顶部栏下方，而是落在页面纵向约一半处。所以标题的纵向闭口要换一种 ——
//
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | 标题 | `intrinsic` 高；宽 `bounded`（内容列） | **`proportional`**：top = 页面高 × 0.5024 / 0.4722 |
//  | 完成图标 | `fixed` 56 / 72（图标点值是视觉常量） | 贴标题底 `pinned` 74 / 100 |
//  | CTA | 高 `bounded`（>= 56/75）；宽 `bounded` 封顶 480 | 贴安全区底 `pinned` 34/81 + 居中 |
//
//  旧的 `[self.titleLabel.topAnchor constraintEqualToAnchor:self.backButton.bottomAnchor]`
//  会把标题放到 y≈108，与稿件的 428 差 320pt —— 因为本页顶部栏是隐藏的，
//  那条 `pinned` 规则的基准（返回键）在这页没有意义。
//

#import "OnboardingDoneViewController.h"
#import "OnboardingStyle.h"
#import "SubscriptionPaywallViewController.h"

@interface OnboardingDoneViewController ()
@property (nonatomic, strong) UIImageView *doneIconView;
@end

@implementation OnboardingDoneViewController

- (NSString *)titleText { return @""; }

// 完成页 CTA 文案（跨稿分档）：手机 "Let's try"、iPad "Continue"。
- (NSString *)ctaText {
    return self.usesTabletDesignValues ? [OnboardingStyle doneCTATextIpad]
                                       : [OnboardingStyle doneCTATextPhone];
}

- (CGFloat)doneTitleFontSize {
    return self.usesTabletDesignValues ? [OnboardingStyle doneTitleFontSizeIpad]
                                       : [OnboardingStyle doneTitleFontSizePhone];
}

- (CGFloat)doneTitleTopRatio {
    return self.usesTabletDesignValues ? [OnboardingStyle doneTitleTopRatioIpad]
                                       : [OnboardingStyle doneTitleTopRatioPhone];
}

- (CGFloat)doneIconSize {
    return self.usesTabletDesignValues ? [OnboardingStyle doneIconSizeIpad]
                                       : [OnboardingStyle doneIconSizePhone];
}

// 图标顶 = 标题底 + 74 / 100。
- (CGFloat)contentTopGap {
    return self.usesTabletDesignValues ? [OnboardingStyle doneIconTopGapIpad]
                                       : [OnboardingStyle doneIconTopGapPhone];
}

#pragma mark - 标题（富文本 + 按页面高度比例定位）

// 完成页标题分两段：「Looks mazing」Medium + 「Pop Color Art is now ready…」Black，
// 两段**同字号**、只差字族。
- (NSAttributedString *)titleAttributedText {
    NSMutableParagraphStyle *para = [[NSMutableParagraphStyle alloc] init];
    para.alignment = NSTextAlignmentCenter;
    para.lineSpacing = self.usesTabletDesignValues ? [OnboardingStyle doneTitleLineSpacingIpad]
                                                   : [OnboardingStyle doneTitleLineSpacingPhone];

    CGFloat size = [self doneTitleFontSize];
    UIColor *color = [OnboardingStyle titleColor];
    UIFont *mediumFont = [OnboardingStyle scaledFont:[OnboardingStyle optionFontOfSize:size]
                                         forTextStyle:UIFontTextStyleTitle2];
    UIFont *blackFont = [OnboardingStyle scaledFont:[OnboardingStyle titleFontOfSize:size]
                                        forTextStyle:UIFontTextStyleTitle2];

    NSMutableAttributedString *text = [[NSMutableAttributedString alloc] init];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:@"Looks mazing\n" attributes:@{
        NSFontAttributeName: mediumFont,
        NSForegroundColorAttributeName: color,
        NSParagraphStyleAttributeName: para,
    }]];
    [text appendAttributedString:[[NSAttributedString alloc]
        initWithString:@"Pop Color Art is now ready for you!"
            attributes:@{
                NSFontAttributeName: blackFont,
                NSForegroundColorAttributeName: color,
                NSParagraphStyleAttributeName: para,
            }]];
    return text;
}

/// 覆盖基类的默认闭口（贴返回键底）：本页顶部栏隐藏，标题改按**页面高度比例**闭合。
/// 手机 428/852 = 0.5024、iPad 510/1080 = 0.4722 —— 两稿各取各的比例。
///
/// 用 `constraintWithItem:attribute:...multiplier:` 而不是 `constraintEqualToAnchor:multiplier:` ——
/// 后者只存在于 `NSLayoutDimension`（宽/高锚点），纵向锚点没有这个变体。
/// `titleLabel.top` 与 `view.bottom` 同处 `self.view` 的坐标系，故
/// `title.top = ratio × view.bottom` 即 `title.top = ratio × 页面高`。
- (NSLayoutConstraint *)titleTopConstraint {
    return [NSLayoutConstraint constraintWithItem:self.titleLabel
                                       attribute:NSLayoutAttributeTop
                                       relatedBy:NSLayoutRelationEqual
                                          toItem:self.view
                                       attribute:NSLayoutAttributeBottom
                                      multiplier:[self doneTitleTopRatio]
                                        constant:0.0];
}

- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    // 富文本不会自动跟随 Dynamic Type（`adjustsFontForContentSizeCategory` 只作用于 `font`），
    // 所以字号档变了要重建一次 attributed string。
    if (previousTraitCollection &&
        previousTraitCollection.preferredContentSizeCategory != self.traitCollection.preferredContentSizeCategory) {
        self.titleLabel.attributedText = [self titleAttributedText];
    }
}

- (void)viewDidLoad {
    self.stepIndex = 7;
    self.totalSteps = 7;
    // 终点页：顶部栏整体收起（返回键 / 进度条 / Skip）。
    self.hidesBackAndSkip = YES;
    [super viewDidLoad];
}

#pragma mark - 完成图标

- (void)buildOptions {
    // 完成图标：生产切图 `onboarding_done_icon`（稿件图层名叫 splash_icon_ok_l，是命名不一致）。
    // 边长是**图标点值尺寸**，属于 `fixed` 视觉常量（跨稿分档 56 / 72），不随窗口缩放。
    UIImageView *icon = [[UIImageView alloc] initWithImage:[UIImage imageNamed:@"onboarding_done_icon"]];
    icon.contentMode = UIViewContentModeScaleAspectFit;
    icon.translatesAutoresizingMaskIntoConstraints = NO;
    [self.optionContainer addSubview:icon];
    self.doneIconView = icon;

    CGFloat side = [self doneIconSize];
    [NSLayoutConstraint activateConstraints:@[
        [icon.centerXAnchor constraintEqualToAnchor:self.optionContainer.centerXAnchor],
        [icon.topAnchor constraintEqualToAnchor:self.optionContainer.topAnchor],
        [icon.widthAnchor constraintEqualToConstant:side],
        [icon.heightAnchor constraintEqualToConstant:side],
        // 容器高由图标闭口（上面 `top` + 这里 `bottom`），滚动区不会留出多余空白。
        [icon.bottomAnchor constraintEqualToAnchor:self.optionContainer.bottomAnchor],
    ]];
}

#pragma mark - 完成页 CTA

// 引导完成 → 进入主 App（订阅付费墙作为当前主入口占位）。
- (void)didTapContinue:(id)sender {
    SubscriptionPaywallViewController *paywall = [[SubscriptionPaywallViewController alloc] init];
    [self.navigationController pushViewController:paywall animated:YES];
}

@end
