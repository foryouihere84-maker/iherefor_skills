//
//  ColorOnboardingViewController.m
//
//  引导步骤 6：色板。6 张 Guide_color_* 完整横条图（已含色块+文字）。
//

#import "ColorOnboardingViewController.h"
#import "OnboardingStyle.h"
#import "OnboardingDoneViewController.h"

@interface ColorOnboardingViewController ()
@property (nonatomic, strong) NSMutableArray<UIView *> *cards;
@end

@implementation ColorOnboardingViewController

- (NSString *)titleText { return @"Which palettes resonates with you the most?"; }
- (Class)nextViewControllerClass { return [OnboardingDoneViewController class]; }

- (void)viewDidLoad {
    self.stepIndex = 6;
    self.totalSteps = 7;
    [super viewDidLoad];
}

- (void)buildOptions {
    // 6 个色板（顺序 Basic→Make up→Pop→Macaron→Flowers→Lively），完整横条图。
    NSArray *items = @[
        @"guide_color_basic",
        @"guide_color_makeup",
        @"guide_color_pop",
        @"guide_color_macaron",
        @"guide_color_flower",
        @"guide_color_lively",
    ];
    // 横条高按**位图自身宽高比**闭合：手机 102/353 = 0.2890、iPad 102/481 = 0.2121。
    CGFloat ratio = self.usesTabletDesignValues ? [OnboardingStyle colorRowHeightRatioIpad]
                                                : [OnboardingStyle colorRowHeightRatioPhone];

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
            [card.topAnchor constraintEqualToAnchor:prev.bottomAnchor constant:[OnboardingStyle colorRowGap]].active = YES;
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
    // **未选中也有描边**：稿件每条横条都是 radius 12 + 1.5pt #DEDEDE，
    // 选中的那一条换成 #5957FF。旧代码只在选中时才画边，未选中是秃的。
    card.layer.borderWidth = [OnboardingStyle optionCardBorderWidth];
    card.layer.borderColor = [OnboardingStyle optionBorderMuted].CGColor;
    card.clipsToBounds = YES;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTap:)];
    [card addGestureRecognizer:tap];

    // 图片三件套：比例（外面的 aspect-ratio 约束）+ 填充模式 + 裁剪语义。
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
