//
//  AgeOnboardingViewController.m
//
//  引导步骤 3：年龄。6 个年龄段单选选项卡。仅手机稿，iPad 走 max-content-width 居中。
//

#import "AgeOnboardingViewController.h"
#import "OnboardingStyle.h"
#import "StyleOnboardingViewController.h"

@interface AgeOnboardingViewController ()
@property (nonatomic, strong) NSMutableArray<UIView *> *cards;
@end

@implementation AgeOnboardingViewController

- (NSString *)titleText { return @"What\u2019s your age?"; }
- (Class)nextViewControllerClass { return [StyleOnboardingViewController class]; }

- (void)viewDidLoad {
    self.stepIndex = 3;
    self.totalSteps = 7;
    [super viewDidLoad];
}

- (void)buildOptions {
    NSArray *opts = @[
        @"✏️ Less than 14",
        @"🎓 14-17",
        @"🖌️ 18-24",
        @"💼 25-34",
        @"🌟 35-44",
        @"🌵 45 or older",
    ];
    self.cards = [NSMutableArray array];
    UIView *prev = nil;
    for (NSString *opt in opts) {
        UIView *card = [self makeCard:opt];
        [self.optionContainer addSubview:card];
        [self.cards addObject:card];
        [NSLayoutConstraint activateConstraints:@[
            // 宽度贴容器两侧（pinned）—— 卡片宽度不由常量决定，容器窄了卡片跟着窄。
            [card.leadingAnchor constraintEqualToAnchor:self.optionContainer.leadingAnchor],
            [card.trailingAnchor constraintEqualToAnchor:self.optionContainer.trailingAnchor],
            // 高度 `>=` 闭合（bounded）：66 是设计下限，动态字体放大时卡片可以变高而不是裁字。
            [card.heightAnchor constraintGreaterThanOrEqualToConstant:[self optionCardHeight]],
        ]];
        if (prev) {
            // 卡片间距是设计常量（10），不是比例 —— 写成字面量。
            [card.topAnchor constraintEqualToAnchor:prev.bottomAnchor constant:[OnboardingStyle optionRowGap]].active = YES;
        } else {
            [card.topAnchor constraintEqualToAnchor:self.optionContainer.topAnchor].active = YES;
        }
        prev = card;
    }
    [prev.bottomAnchor constraintEqualToAnchor:self.optionContainer.bottomAnchor].active = YES;
}

- (UIView *)makeCard:(NSString *)text {
    UIView *card = [[UIView alloc] init];
    card.backgroundColor = [OnboardingStyle optionCardBackground];
    card.layer.cornerRadius = [OnboardingStyle optionCardRadius];
    card.layer.borderWidth = [OnboardingStyle optionCardBorderWidth];
    card.layer.borderColor = [OnboardingStyle optionBorderMuted].CGColor;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTap:)];
    [card addGestureRecognizer:tap];

    CGFloat fontSize = self.usesTabletDesignValues ? [OnboardingStyle optionFontSizeIpad]
                                                   : [OnboardingStyle optionFontSizePhone];
    UILabel *label = [[UILabel alloc] init];
    label.text = text;
    label.font = [OnboardingStyle scaledFont:[OnboardingStyle optionFontOfSize:fontSize]
                                 forTextStyle:[OnboardingStyle optionTextStyle]];
    label.adjustsFontForContentSizeCategory = YES;
    label.textColor = [OnboardingStyle titleColor];
    label.numberOfLines = 0;   // 大字号 / 长文案换行，不截断
    label.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:label];
    [NSLayoutConstraint activateConstraints:@[
        [label.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:16.0],
        [label.trailingAnchor constraintLessThanOrEqualToAnchor:card.trailingAnchor constant:-16.0],
        [label.centerYAnchor constraintEqualToAnchor:card.centerYAnchor],
    ]];
    return card;
}

- (void)didTap:(UITapGestureRecognizer *)tap {
    for (UIView *c in self.cards) {
        c.layer.borderColor = (c == tap.view ? [OnboardingStyle optionBorderSelected] : [OnboardingStyle optionBorderMuted]).CGColor;
    }
    self.hasSelection = YES;
}

@end
