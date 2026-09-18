//
//  BrushOnboardingViewController.m
//
//  引导步骤 5：笔刷。7 张 Guide_brush_* 完整横条图（已含图标+文字）。
//

#import "BrushOnboardingViewController.h"
#import "OnboardingStyle.h"
#import "ColorOnboardingViewController.h"

@interface BrushOnboardingViewController ()
@property (nonatomic, strong) NSMutableArray<UIView *> *cards;
@end

@implementation BrushOnboardingViewController

- (NSString *)titleText { return @"Which brushes are you most excited to try?"; }
- (Class)nextViewControllerClass { return [ColorOnboardingViewController class]; }

- (void)viewDidLoad {
    self.stepIndex = 5;
    self.totalSteps = 7;
    [super viewDidLoad];
}

- (void)buildOptions {
    // 7 个笔刷：图片名（完整横条图，含图标+文字标签）。
    NSArray *items = @[
        @"guide_brush_paint",
        @"guide_brush_pencil",
        @"guide_brush_watercolor",
        @"guide_brush_pastel",
        @"guide_brush_spray",
        @"guide_brush_marker",
        @"guide_brush_flat",
    ];
    // 横条高度按**位图自身宽高比**闭合（手机 86/353 = 0.2436、iPad 98/481 = 0.2037，
    // 两稿比例不同，各取各的比值）：横条宽度被容器闭合，高度随之求解 ——
    // 不再写 `equalToConstant 86/98`，窄窗口下横条整体缩小而不是被裁掉或拉伸。
    CGFloat ratio = self.usesTabletDesignValues ? [OnboardingStyle brushRowHeightRatioIpad]
                                                : [OnboardingStyle brushRowHeightRatioPhone];

    self.cards = [NSMutableArray array];
    UIView *prev = nil;
    for (NSString *imageName in items) {
        UIView *card = [self makeCard:imageName];
        [self.optionContainer addSubview:card];
        [self.cards addObject:card];
        [NSLayoutConstraint activateConstraints:@[
            [card.leadingAnchor constraintEqualToAnchor:self.optionContainer.leadingAnchor],
            [card.trailingAnchor constraintEqualToAnchor:self.optionContainer.trailingAnchor],
            [card.heightAnchor constraintEqualToAnchor:card.widthAnchor multiplier:ratio],
        ]];
        if (prev) {
            // 间距设计常量 10（手机 stride 96 - 行高 86）。
            [card.topAnchor constraintEqualToAnchor:prev.bottomAnchor constant:[OnboardingStyle brushRowGap]].active = YES;
        } else {
            [card.topAnchor constraintEqualToAnchor:self.optionContainer.topAnchor].active = YES;
        }
        prev = card;
    }
    [prev.bottomAnchor constraintEqualToAnchor:self.optionContainer.bottomAnchor].active = YES;
}

- (UIView *)makeCard:(NSString *)imageName {
    UIView *card = [[UIView alloc] init];
    card.backgroundColor = [OnboardingStyle optionCardBackground];
    card.layer.cornerRadius = [OnboardingStyle optionCardRadius];
    card.clipsToBounds = YES;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTap:)];
    [card addGestureRecognizer:tap];

    // 完整横条图（含图标+文字），铺满卡片。
    // 图片三件套：比例（外面那条 aspect-ratio 约束）+ 填充模式 + 裁剪语义。
    // 用 ScaleAspectFit 而不是 ScaleToFill：比例的出处是资源本身，
    // 万一以后换成别的比例的切图，Fit 是等比缩，Fill 会拉变形。
    UIImageView *img = [[UIImageView alloc] initWithImage:[UIImage imageNamed:imageName]];
    img.contentMode = UIViewContentModeScaleAspectFit;
    img.clipsToBounds = YES;
    img.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:img];

    [NSLayoutConstraint activateConstraints:@[
        [img.topAnchor constraintEqualToAnchor:card.topAnchor],
        [img.leadingAnchor constraintEqualToAnchor:card.leadingAnchor],
        [img.trailingAnchor constraintEqualToAnchor:card.trailingAnchor],
        [img.bottomAnchor constraintEqualToAnchor:card.bottomAnchor],
    ]];
    return card;
}

- (void)didTap:(UITapGestureRecognizer *)tap {
    for (UIView *c in self.cards) {
        // 只换颜色，不换宽度 —— 稿件选中 / 未选中都是 1.5pt。
        c.layer.borderColor = (c == tap.view ? [OnboardingStyle optionBorderSelected]
                                            : [OnboardingStyle optionBorderMuted]).CGColor;
    }
    self.hasSelection = YES;
}

@end
