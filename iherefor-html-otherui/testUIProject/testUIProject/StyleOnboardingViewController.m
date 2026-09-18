//
//  StyleOnboardingViewController.m
//
//  引导步骤 4：风格。8 张 Guide 缩略图网格。
//
//  **布局口径**（闭合依据见 OnboardingStyle.h 的「风格页网格」段）：
//
//  | 元素 | 尺寸轴 | 位置轴 |
//  |---|---|---|
//  | 网格 | 宽 `pinned`（贴容器两侧）；列数由**宽度档**定 | 贴容器四边（`pinned`） |
//  | 卡片 | 宽 `equal`（行内 `fillEqually` 等分）；高 `aspect-ratio`（146/170） | 行内顺序排布 |
//  | 缩略图 | 铺满卡片（`pinned` 四边） | — |
//  | 标签遮罩 | 高 `proportional`（卡片宽 × 0.4） | 底贴卡片（`pinned`） |
//  | 标签文字 | `intrinsic`（文字撑开） | 底对齐卡片底（`pinned` 10/16） |
//
//  **不写** 170/200 这类卡片尺寸常量：设计机型上 2 列 → (353-13)/2 = 170、
//  3 列 → (640-40)/3 = 200，与稿件逐字相同；窄窗口（iPad 分屏 1/3、Slide Over）
//  下整格等比缩小，而不是溢出或拉伸。
//

#import "StyleOnboardingViewController.h"
#import "OnboardingStyle.h"
#import "BrushOnboardingViewController.h"

#pragma mark - 遮罩视图

/// 用 `CAGradientLayer` 作 backing layer：尺寸随 Auto Layout 自动跟随，
/// 不需要在 `layoutSubviews` 里手工同步 `frame`（那样会漏掉每一次尺寸变化）。
@interface StyleCardScrimView : UIView
@end

@implementation StyleCardScrimView
+ (Class)layerClass { return [CAGradientLayer class]; }
@end

#pragma mark -

@interface StyleOnboardingViewController ()

/// 8 个风格项：[切图名, 标题]
@property (nonatomic, strong) NSArray<NSArray<NSString *> *> *styles;
/// 当前网格里真实的卡片（占位视图不入内），供选中态刷新
@property (nonatomic, strong) NSMutableArray<UIView *> *cards;
@property (nonatomic, strong) UIStackView *gridStack;
/// 当前列数，用于判断宽度档变化时是否要重建网格
@property (nonatomic, assign) NSInteger currentColumns;

@end

@implementation StyleOnboardingViewController

- (NSString *)titleText { return @"What type of artwork do you enjoy coloring\uff1f"; }
- (Class)nextViewControllerClass { return [BrushOnboardingViewController class]; }

/// 网格外层封顶改用 640（3×200 + 2×20）。手机档下不生效（353 < 640），
/// 宽档下把 3 列网格收在 640 并居中 —— 与 iPad 稿件逐字一致。
- (CGFloat)maxContentWidth { return [OnboardingStyle styleGridMaxContentWidth]; }

- (void)viewDidLoad {
    self.stepIndex = 4;
    self.totalSteps = 7;
    // 手机稿 8 张卡片排到 y=829，最后一行会滑到 CTA 底下 ——
    // 稿件在 CTA 上方铺了一条 393×190 的遮罩（y 662 起，正好是 CTA 顶 −66）。
    self.showsFooterScrim = YES;
    [super viewDidLoad];
}

#pragma mark - 网格

/// 行/列间距（跨稿分档）：手机 13、iPad 20。
/// 间距是**视觉常量**（13/393 与 20/810 不成比例），所以按稿取，不按宽度档缩放。
- (CGFloat)gridGap {
    return self.usesTabletDesignValues ? [OnboardingStyle styleGridGapIpad]
                                       : [OnboardingStyle styleGridGapPhone];
}

- (void)buildOptions {
    self.styles = @[
        @[@"guide_style_animal",  @"Animal"],
        @[@"guide_style_people",  @"People"],
        @[@"guide_style_food",    @"Food"],
        @[@"guide_style_flower",  @"Flower"],
        @[@"guide_style_manga",   @"Manga"],
        @[@"guide_style_cute",    @"Cute"],
        @[@"guide_style_mandala", @"Mandala"],
        @[@"guide_style_easy",    @"Easy"],
    ];
    self.cards = [NSMutableArray array];

    self.gridStack = [[UIStackView alloc] init];
    self.gridStack.axis = UILayoutConstraintAxisVertical;
    self.gridStack.alignment = UIStackViewAlignmentFill;
    self.gridStack.distribution = UIStackViewDistributionFill;
    self.gridStack.spacing = [self gridGap];
    self.gridStack.translatesAutoresizingMaskIntoConstraints = NO;
    [self.optionContainer addSubview:self.gridStack];

    // 网格贴容器四边（pinned）。容器宽度由基类的「内容内边距 + 封顶」闭合，
    // 网格跟着容器走，自己不声明宽度。
    [NSLayoutConstraint activateConstraints:@[
        [self.gridStack.topAnchor constraintEqualToAnchor:self.optionContainer.topAnchor],
        [self.gridStack.leadingAnchor constraintEqualToAnchor:self.optionContainer.leadingAnchor],
        [self.gridStack.trailingAnchor constraintEqualToAnchor:self.optionContainer.trailingAnchor],
        [self.gridStack.bottomAnchor constraintEqualToAnchor:self.optionContainer.bottomAnchor],
    ]];

    [self rebuildGrid];
    self.currentColumns = [OnboardingStyle styleColumnCountForWidthClass:self.widthClass];
}

/// 按当前宽度档重建行。**列数变化必须重建** —— 8 张卡片从 2 列切到 3 列，
/// 行数会从 4 变 3，无法靠改约束完成。
- (void)rebuildGrid {
    for (UIView *view in [self.gridStack.arrangedSubviews copy]) {
        [self.gridStack removeArrangedSubview:view];
        [view removeFromSuperview];
    }
    [self.cards removeAllObjects];

    NSInteger columns = [OnboardingStyle styleColumnCountForWidthClass:self.widthClass];
    NSInteger total = (NSInteger)self.styles.count;
    NSInteger rows = (total + columns - 1) / columns;
    NSInteger index = 0;

    for (NSInteger r = 0; r < rows; r++) {
        UIStackView *rowStack = [[UIStackView alloc] init];
        rowStack.axis = UILayoutConstraintAxisHorizontal;
        // 兄弟等宽（`equal`）：卡片宽度由行宽等分闭合，不由常量决定。
        rowStack.distribution = UIStackViewDistributionFillEqually;
        rowStack.alignment = UIStackViewAlignmentFill;
        rowStack.spacing = [self gridGap];

        NSInteger inRow = MIN(columns, total - index);
        for (NSInteger c = 0; c < columns; c++) {
            if (c < inRow) {
                NSArray<NSString *> *item = self.styles[index];
                UIView *card = [self makeCardWithImageName:item[0] title:item[1]];
                [rowStack addArrangedSubview:card];
                [self.cards addObject:card];
                index++;
            } else {
                // 末行不足列数（8 张卡 3 列时末行只有 2 张）：补一个透明占位，
                // 让已排卡片与上面各列**等宽**，而不是被两端拉伸填满整行。
                UIView *spacer = [[UIView alloc] init];
                spacer.backgroundColor = UIColor.clearColor;
                spacer.userInteractionEnabled = NO;
                [rowStack addArrangedSubview:spacer];
            }
        }
        [self.gridStack addArrangedSubview:rowStack];
    }
}

/// 宽度档变化时重排：列数变了就重建网格。
- (void)applyWidthClass {
    [super applyWidthClass];

    NSInteger columns = [OnboardingStyle styleColumnCountForWidthClass:self.widthClass];
    if (self.gridStack && columns != self.currentColumns) {
        self.currentColumns = columns;
        [self rebuildGrid];
    }
}

#pragma mark - 卡片

- (UIView *)makeCardWithImageName:(NSString *)imageName title:(NSString *)title {
    UIView *card = [[UIView alloc] init];
    card.backgroundColor = [OnboardingStyle optionCardBackground];
    // 圆角 12：稿件卡片是 `蒙版`（radius [12]），与选项卡同值。
    card.layer.cornerRadius = [OnboardingStyle optionCardRadius];
    // 卡片同时充当缩略图与遮罩的裁剪容器 —— 遮罩底角与卡片同心（稿件 `radius [0,0,12,12]`）
    // 就是靠这一层裁剪得到的，不需要单独给遮罩画圆角。
    card.clipsToBounds = YES;
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.userInteractionEnabled = YES;
    UITapGestureRecognizer *tap =
        [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapCard:)];
    [card addGestureRecognizer:tap];

    // 高度按**宽高比**闭合：卡片宽由行内等分定，高度随之求解（146/170 = 172/200 ≈ 0.86）。
    [card.heightAnchor constraintEqualToAnchor:card.widthAnchor
                                    multiplier:[OnboardingStyle styleCardHeightRatio]].active = YES;

    // 缩略图：铺满整张卡片。
    UIImageView *img = [[UIImageView alloc] initWithImage:[UIImage imageNamed:imageName]];
    img.contentMode = UIViewContentModeScaleAspectFill;
    img.clipsToBounds = YES;
    img.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:img];

    // 底部渐变遮罩：白字压在图上传，需要它保证可读性。
    // 高度 = 卡片宽 × 0.4（手机 68/170、iPad 80/200，**两稿精确同值**）。
    StyleCardScrimView *scrim = [[StyleCardScrimView alloc] init];
    scrim.userInteractionEnabled = NO;
    scrim.translatesAutoresizingMaskIntoConstraints = NO;
    CAGradientLayer *gradient = (CAGradientLayer *)scrim.layer;
    gradient.colors = @[
        (id)[[OnboardingStyle styleCardScrimColor] colorWithAlphaComponent:0.0].CGColor,
        (id)[[OnboardingStyle styleCardScrimColor]
             colorWithAlphaComponent:[OnboardingStyle styleCardScrimMaxAlpha]].CGColor,
    ];
    gradient.startPoint = CGPointMake(0.5, 0.0);
    gradient.endPoint   = CGPointMake(0.5, 1.0);
    [card addSubview:scrim];

    CGFloat fontSize = self.usesTabletDesignValues ? [OnboardingStyle styleCardLabelFontSizeIpad]
                                                   : [OnboardingStyle styleCardLabelFontSizePhone];
    UILabel *label = [[UILabel alloc] init];
    label.text = title;
    label.font = [OnboardingStyle scaledFont:[OnboardingStyle optionFontOfSize:fontSize]
                                 forTextStyle:[OnboardingStyle optionTextStyle]];
    label.adjustsFontForContentSizeCategory = YES;
    label.textColor = [OnboardingStyle styleCardLabelColor];
    label.textAlignment = NSTextAlignmentCenter;
    label.numberOfLines = 0;
    label.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:label];

    CGFloat labelBottomInset = self.usesTabletDesignValues ? [OnboardingStyle styleCardLabelBottomInsetIpad]
                                                           : [OnboardingStyle styleCardLabelBottomInsetPhone];

    [NSLayoutConstraint activateConstraints:@[
        // 缩略图铺满（pinned 四边）。
        [img.topAnchor constraintEqualToAnchor:card.topAnchor],
        [img.leadingAnchor constraintEqualToAnchor:card.leadingAnchor],
        [img.trailingAnchor constraintEqualToAnchor:card.trailingAnchor],
        [img.bottomAnchor constraintEqualToAnchor:card.bottomAnchor],

        // 遮罩：左右与底贴卡片（pinned），高按卡片宽比例闭合（proportional）。
        [scrim.leadingAnchor constraintEqualToAnchor:card.leadingAnchor],
        [scrim.trailingAnchor constraintEqualToAnchor:card.trailingAnchor],
        [scrim.bottomAnchor constraintEqualToAnchor:card.bottomAnchor],
        [scrim.heightAnchor constraintEqualToAnchor:card.widthAnchor
                                         multiplier:[OnboardingStyle styleCardLabelStripHeightRatio]],

        // 标签：底对齐卡片底（pinned，视觉常量 10/16），水平居中并留 8pt 不贴边。
        [label.centerXAnchor constraintEqualToAnchor:card.centerXAnchor],
        [label.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-labelBottomInset],
        [label.leadingAnchor constraintGreaterThanOrEqualToAnchor:card.leadingAnchor constant:8.0],
        [label.trailingAnchor constraintLessThanOrEqualToAnchor:card.trailingAnchor constant:-8.0],
    ]];

    return card;
}

- (void)didTapCard:(UITapGestureRecognizer *)tap {
    for (UIView *card in self.cards) {
        BOOL selected = (card == tap.view);
        // 选中描边：稿件 #5957FF / 1.5pt（每页恰有一张卡片用它，即当前选中项）。
        card.layer.borderWidth = selected ? [OnboardingStyle optionCardBorderWidth] : 0.0;
        card.layer.borderColor = selected ? [OnboardingStyle optionBorderSelected].CGColor
                                          : [UIColor clearColor].CGColor;
    }
    self.hasSelection = YES;
    self.selectedValue = tap.view;
}

@end
