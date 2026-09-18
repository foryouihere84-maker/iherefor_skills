//
//  PurposeOnboardingViewController.m
//  testUIProject
//
//  引导步骤 1：目的。6 个 emoji 单选选项卡。
//

#import "PurposeOnboardingViewController.h"
#import "OnboardingStyle.h"
#import "GenderOnboardingViewController.h"

@interface PurposeOnboardingViewController ()

@property (nonatomic, strong) NSMutableArray<UIView *> *optionCards;
@property (nonatomic, strong) NSArray<NSString *> *options;

@end

@implementation PurposeOnboardingViewController

- (NSString *)titleText { return @"How can we help you?"; }
- (Class)nextViewControllerClass { return [GenderOnboardingViewController class]; }

- (void)viewDidLoad {
    self.stepIndex = 1;
    self.totalSteps = 7;
    [super viewDidLoad];
}

- (void)buildOptions {
    self.options = @[
        @"🌸 Relax myself",
        @"😜 Have fun",
        @"🎨 Express my creativity",
        @"🧠 Disconnect my brain",
        @"🖊️ Develop my coloring skills",
        @"👀 Other",
    ];
    self.optionCards = [NSMutableArray array];

    UIView *prev = nil;
    for (NSString *opt in self.options) {
        UIView *card = [self makeOptionCard:opt];
        [self.optionContainer addSubview:card];
        [self.optionCards addObject:card];

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

- (UIView *)makeOptionCard:(NSString *)text {
    UIView *card = [[UIView alloc] init];
    card.backgroundColor = [UIColor whiteColor];
    card.layer.cornerRadius = [OnboardingStyle optionCardRadius];
    card.layer.borderWidth = 2.0;
    card.layer.borderColor = [OnboardingStyle optionBorderMuted].CGColor;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;

    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapOption:)];
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

- (void)didTapOption:(UITapGestureRecognizer *)tap {
    UIView *tapped = tap.view;
    for (UIView *card in self.optionCards) {
        BOOL selected = (card == tapped);
        // 选项卡的选中态只换**描边颜色**（#5957FF），描边宽度保持 1.5 不变 ——
        // 旧代码这里写 `selected ? 2.0 : 2.0`，两个分支同值，是个无效分支。
        card.layer.borderColor = (selected ? [OnboardingStyle optionBorderSelected] : [OnboardingStyle optionBorderMuted]).CGColor;
    }
    self.hasSelection = YES;
    self.selectedValue = tapped;
}

@end
