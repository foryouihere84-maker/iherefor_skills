//
//  PurposeSelectionViewController.m
//  testUIProject
//
//  Purpose-selection onboarding screen (Lanhu "目的" cc79645f + "目的-iPad" 28d3d7b5).
//
//  Two-device adaptation (option X — two full specs, not a scale-up): the phone and
//  iPad boards are two COMPLETE independent designs, not one board scaled. They
//  differ in canvas (393x852 vs 810x1080), font sizes (headline 24→30, Skip 14→18,
//  Continue 16→20), card width (353→480), card order, CTA size (347x56→480x75) and
//  hero height (365→394). This view switches between the two full specs on
//  `horizontalSizeClass`: compact → phone spec, regular → iPad spec.
//
//  All coordinates below are the board's own canvas space (phone 393x852, iPad
//  810x1080), taken from the RENDERED page-facts (not the design_document layer
//  tree — the iPad design_document has a negative-offset root `(-64,79.5)` and
//  missing text nodes, so its layer rects are NOT usable as absolute coords; the
//  rendered HTML/*.css is the truth).
//
//  System-bars policy (underlap): hero artwork paints from y=0, mock status bar is
//  a placeholder, not implemented.
//

#import "PurposeSelectionViewController.h"
#import "PurposeSelectionStyle.h"

static NSString *const kAssetHeroBackground = @"age_hero_background"; // same art as age/brush
static NSString *const kAssetNavBack = @"age_nav_back";

static const CGFloat kCardCornerRadius = 12.0;
static const CGFloat kCardBorderWidth = 1.5;
static const CGFloat kProgressCornerRadius = 3.0;
static const CGFloat kCtaCornerRadius = 28.0;

/// One option row: emoji + label + board-space design frame.
typedef struct {
    __unsafe_unretained NSString *emoji;
    __unsafe_unretained NSString *label;
    CGFloat y;
    CGFloat height;
    CGFloat width;
    CGFloat x;
} PurposeOptionRow;

/// Phone board (393x852). Rendered order: Express (overhangs box_6 top), Relax,
/// Have fun, Disconnect, Develop, Other.
static const PurposeOptionRow kPhoneOptionRows[] = {
    {@"🎨", @"Express\u00A0my\u00A0creativity",           358.0, 66.0, 353.0, 20.0},
    {@"🌸", @"Relax\u00A0myself",                          206.0, 65.0, 353.0, 20.0},
    {@"😜", @"Have\u00A0fun",                              281.0, 65.0, 353.0, 20.0},
    {@"🧠", @"Disconnect\u00A0my\u00A0brain",              434.0, 65.0, 353.0, 20.0},
    {@"🖊️", @"Develop\u00A0my\u00A0coloring\u00A0skills",   509.0, 65.0, 353.0, 20.0},
    {@"👀", @"Other",                                      584.0, 65.0, 353.0, 20.0},
};
static const NSUInteger kPhoneOptionRowCount = sizeof(kPhoneOptionRows) / sizeof(kPhoneOptionRows[0]);

/// iPad board (810x1080). Rendered order (from index.html DOM): Relax, Have fun,
/// Express, Disconnect, Develop, Other. Cards 480 wide at x=165.
static const PurposeOptionRow kIpadOptionRows[] = {
    {@"🌸", @"Relax\u00A0myself",                          248.0, 65.0, 480.0, 165.0},
    {@"😜", @"Have\u00A0fun",                              323.0, 65.0, 480.0, 165.0},
    {@"🎨", @"Express\u00A0my\u00A0creativity",            398.0, 65.0, 480.0, 165.0},
    {@"🧠", @"Disconnect\u00A0my\u00A0brain",              473.0, 65.0, 480.0, 165.0},
    {@"🖊️", @"Develop\u00A0my\u00A0coloring\u00A0skills",   548.0, 65.0, 480.0, 165.0},
    {@"👀", @"Other",                                      623.0, 65.0, 480.0, 165.0},
};
static const NSUInteger kIpadOptionRowCount = sizeof(kIpadOptionRows) / sizeof(kIpadOptionRows[0]);

static const CGFloat kPhoneCanvasWidth = 393.0;
static const CGFloat kPhoneCanvasHeight = 852.0;
static const CGFloat kIpadCanvasWidth = 810.0;
static const CGFloat kIpadCanvasHeight = 1080.0;

@interface PurposeSelectionViewController ()
@property(nonatomic, strong) UIView *canvasView;
@property(nonatomic, strong) UIImageView *heroBackgroundView;
@property(nonatomic, strong) UIImageView *navBackView;
@property(nonatomic, strong) UIView *progressTrackView;
@property(nonatomic, strong) UIView *progressFillView;
@property(nonatomic, strong) UILabel *skipLabel;
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UIView *ctaBackgroundView;
@property(nonatomic, strong) UILabel *ctaLabel;
@property(nonatomic, strong) NSMutableArray<UIView *> *optionCards;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@end

@implementation PurposeSelectionViewController

#pragma mark - Trait-aware board selection

- (BOOL)isRegularWidth {
    return self.traitCollection.horizontalSizeClass == UIUserInterfaceSizeClassRegular;
}

- (CGSize)canvasDesignSize {
    return self.isRegularWidth
        ? CGSizeMake(kIpadCanvasWidth, kIpadCanvasHeight)
        : CGSizeMake(kPhoneCanvasWidth, kPhoneCanvasHeight);
}

- (const PurposeOptionRow *)optionRows {
    return self.isRegularWidth ? kIpadOptionRows : kPhoneOptionRows;
}

- (NSUInteger)optionRowCount {
    return self.isRegularWidth ? kIpadOptionRowCount : kPhoneOptionRowCount;
}

- (CGFloat)heroDesignHeight {
    return self.isRegularWidth ? 394.0 : 365.0;
}

#pragma mark - Trait-aware typography (option X: iPad board has larger type)

- (UIFont *)headlineFont {
    return self.isRegularWidth
        ? PurposeSelectionStyle.headlineFontIpad      // 30
        : PurposeSelectionStyle.headlineFont;         // 24
}

- (UIFont *)skipFont {
    return self.isRegularWidth
        ? PurposeSelectionStyle.skipFontIpad          // 18
        : PurposeSelectionStyle.skipFont;             // 14
}

- (UIFont *)ctaFont {
    return self.isRegularWidth
        ? PurposeSelectionStyle.ctaFontIpad           // 20
        : PurposeSelectionStyle.ctaFont;              // 16
}

- (UIFont *)optionFont {
    return PurposeSelectionStyle.optionFont;  // 18 in both boards
}

- (CGRect)ctaDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(165.0, 898.0, 480.0, 75.0)
        : CGRectMake(26.0, 725.0, 347.0, 56.0);
}

- (CGRect)titleDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(244.0, 125.0, 322.0, 36.0)
        : CGRectMake(68.0, 108.0, 258.0, 29.0);
}

- (CGRect)skipDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(735.0, 62.0, 35.0, 34.0)
        : CGRectMake(346.0, 60.0, 27.0, 24.0);
}

- (CGRect)backDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(48.0, 46.0, 44.0, 44.0)
        : CGRectMake(12.0, 52.0, 32.0, 32.0);
}

- (CGRect)progressDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(96.0, 66.0, 482.0, 8.0)
        : CGRectMake(81.0, 65.0, 232.0, 6.0);
}

- (CGFloat)progressFillWidth {
    return self.isRegularWidth ? 32.0 : 24.0;
}

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];

    self.view.backgroundColor = PurposeSelectionStyle.pageBackgroundColor;
    self.view.accessibilityIdentifier = @"purpose-selection";
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    NSLog(@"IHEREFOR_RUNTIME_SCREEN_BOUNDS width=%.4f height=%.4f scale=%.4f nativeScale=%.4f",
          UIScreen.mainScreen.bounds.size.width, UIScreen.mainScreen.bounds.size.height,
          UIScreen.mainScreen.scale, UIScreen.mainScreen.nativeScale);

    [self buildRegions];
}

- (UIStatusBarStyle)preferredStatusBarStyle {
    return UIStatusBarStyleDarkContent;
}

- (void)traitCollectionDidChange:(UITraitCollection *)previousTraitCollection {
    [super traitCollectionDidChange:previousTraitCollection];
    if (self.traitCollection.horizontalSizeClass != previousTraitCollection.horizontalSizeClass) {
        [self teardownRegions];
        [self buildRegions];
    }
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];

    UIEdgeInsets insets = self.view.safeAreaInsets;
    CGSize viewSize = self.view.bounds.size;
    CGSize canvas = [self canvasDesignSize];
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f safeTop=%.4f safeBottom=%.4f "
          @"canvasDesignW=%.4f canvasDesignH=%.4f sizeClass=%ld policy=fit",
          viewSize.width, viewSize.height, insets.top, insets.bottom,
          canvas.width, canvas.height, (long)self.traitCollection.horizontalSizeClass);

    [self logRegionFrames];
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY page=purpose-selection sizeClass=%ld",
          (long)self.traitCollection.horizontalSizeClass);
    [PurposeSelectionStyle logClosureCounters];
    [self logRegionFrames];
}

#pragma mark - Region assembly

- (void)teardownRegions {
    self.hasBuiltRegions = NO;
    [self.canvasView removeFromSuperview];
    self.canvasView = nil;
    self.heroBackgroundView = nil;
    self.navBackView = nil;
    self.progressTrackView = nil;
    self.progressFillView = nil;
    self.skipLabel = nil;
    self.titleLabel = nil;
    self.ctaBackgroundView = nil;
    self.ctaLabel = nil;
    self.optionCards = nil;
}

- (void)buildRegions {
    if (self.hasBuiltRegions) return;
    self.hasBuiltRegions = YES;

    CGSize canvasDesign = [self canvasDesignSize];
    CGFloat aspect = canvasDesign.height / canvasDesign.width;

    self.canvasView = [[UIView alloc] initWithFrame:CGRectZero];
    self.canvasView.backgroundColor = PurposeSelectionStyle.pageBackgroundColor;
    self.canvasView.clipsToBounds = YES;
    self.canvasView.accessibilityIdentifier = @"purposeSelection.canvas";
    [self.view addSubview:self.canvasView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle fitCanvas:self.canvasView
                                                                 insideView:self.view
                                                                aspectRatio:aspect]];

    self.heroBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetHeroBackground]];
    self.heroBackgroundView.contentMode = UIViewContentModeScaleToFill;
    self.heroBackgroundView.accessibilityIdentifier = @"purposeSelection.hero";
    [self.canvasView addSubview:self.heroBackgroundView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.heroBackgroundView
                                                                      parent:self.canvasView
                                                                 designFrame:CGRectMake(0, 0, canvasDesign.width, [self heroDesignHeight])
                                                            parentDesignSize:canvasDesign]];

    [self buildNavRow];
    [self buildTitle];
    [self buildOptionCards];
    [self buildContinueCta];

    [self connectInteractions];
}

- (void)buildNavRow {
    CGSize canvasDesign = [self canvasDesignSize];
    CGRect skipFrame = [self skipDesignFrame];
    CGRect backFrame = [self backDesignFrame];
    CGRect progressFrame = [self progressDesignFrame];

    self.navBackView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetNavBack]];
    self.navBackView.contentMode = UIViewContentModeScaleToFill;
    self.navBackView.userInteractionEnabled = YES;
    self.navBackView.accessibilityIdentifier = @"purposeSelection.back";
    [self.canvasView addSubview:self.navBackView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.navBackView
                                                                      parent:self.canvasView
                                                                 designFrame:backFrame
                                                            parentDesignSize:canvasDesign
                                                                    sizeMode:PurposeClosureSizeIntrinsic
                                                                      anchor:PurposeClosureAnchorLeading]];

    self.progressTrackView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressTrackView.backgroundColor = [UIColor colorWithWhite:22/255.0 alpha:0.2];
    self.progressTrackView.layer.cornerRadius = kProgressCornerRadius;
    self.progressTrackView.layer.masksToBounds = YES;
    self.progressTrackView.accessibilityIdentifier = @"purposeSelection.progressTrack";
    [self.canvasView addSubview:self.progressTrackView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.progressTrackView
                                                                      parent:self.canvasView
                                                                 designFrame:progressFrame
                                                            parentDesignSize:canvasDesign]];

    self.progressFillView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressFillView.backgroundColor = [UIColor colorWithWhite:22/255.0 alpha:1];
    self.progressFillView.layer.cornerRadius = kProgressCornerRadius;
    self.progressFillView.layer.masksToBounds = YES;
    self.progressFillView.accessibilityIdentifier = @"purposeSelection.progressFill";
    [self.progressTrackView addSubview:self.progressFillView];
    self.progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.progressFillView.leadingAnchor constraintEqualToAnchor:self.progressTrackView.leadingAnchor],
        [self.progressFillView.topAnchor constraintEqualToAnchor:self.progressTrackView.topAnchor],
        [self.progressFillView.bottomAnchor constraintEqualToAnchor:self.progressTrackView.bottomAnchor],
        [self.progressFillView.widthAnchor constraintEqualToConstant:[self progressFillWidth]],
    ]];

    self.skipLabel = [[UILabel alloc] init];
    self.skipLabel.text = @"Skip";
    self.skipLabel.font = [self skipFont];
    self.skipLabel.textColor = PurposeSelectionStyle.skipTextColor;
    self.skipLabel.textAlignment = NSTextAlignmentLeft;
    self.skipLabel.userInteractionEnabled = YES;
    self.skipLabel.accessibilityIdentifier = @"purposeSelection.skip";
    [self.canvasView addSubview:self.skipLabel];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.skipLabel
                                                                      parent:self.canvasView
                                                                 designFrame:skipFrame
                                                            parentDesignSize:canvasDesign
                                                                    sizeMode:PurposeClosureSizeIntrinsic
                                                                      anchor:PurposeClosureAnchorLeading]];
}

- (void)buildTitle {
    CGSize canvasDesign = [self canvasDesignSize];
    CGRect frame = [self titleDesignFrame];

    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.text = @"How\u00A0can\u00A0we\u00A0help\u00A0you?";
    self.titleLabel.font = [self headlineFont];
    self.titleLabel.textColor = PurposeSelectionStyle.primaryTextColor;
    self.titleLabel.textAlignment = NSTextAlignmentLeft;
    self.titleLabel.accessibilityIdentifier = @"purposeSelection.title";
    [self.canvasView addSubview:self.titleLabel];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.titleLabel
                                                                      parent:self.canvasView
                                                                 designFrame:frame
                                                            parentDesignSize:canvasDesign
                                                                    sizeMode:PurposeClosureSizeIntrinsic
                                                                      anchor:PurposeClosureAnchorLeading]];
}

- (UIView *)buildOptionCardAtIndex:(NSUInteger)index {
    CGSize canvasDesign = [self canvasDesignSize];
    const PurposeOptionRow *rows = [self optionRows];
    PurposeOptionRow row = rows[index];

    UIView *card = [[UIView alloc] init];
    card.backgroundColor = PurposeSelectionStyle.cardBackgroundColor;
    card.layer.cornerRadius = kCardCornerRadius;
    card.layer.borderWidth = kCardBorderWidth;
    card.layer.borderColor = PurposeSelectionStyle.cardBorderColor.CGColor;
    card.accessibilityIdentifier = [NSString stringWithFormat:@"purposeSelection.card%lu", (unsigned long)index];
    card.userInteractionEnabled = YES;
    [self.canvasView addSubview:card];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:card
                                                                      parent:self.canvasView
                                                                 designFrame:CGRectMake(row.x, row.y, row.width, row.height)
                                                            parentDesignSize:canvasDesign]];

    UILabel *label = [[UILabel alloc] init];
    label.numberOfLines = 1;
    label.userInteractionEnabled = NO;
    UIFont *optionFont = [self optionFont];
    NSMutableAttributedString *text = [[NSMutableAttributedString alloc] init];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:row.emoji
                                                                 attributes:@{
        NSFontAttributeName: [UIFont systemFontOfSize:18.0],
        NSForegroundColorAttributeName: PurposeSelectionStyle.primaryTextColor,
    }]];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:@"\u00A0"
                                                                 attributes:@{
        NSFontAttributeName: optionFont,
        NSForegroundColorAttributeName: PurposeSelectionStyle.primaryTextColor,
    }]];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:row.label
                                                                 attributes:@{
        NSFontAttributeName: optionFont,
        NSForegroundColorAttributeName: PurposeSelectionStyle.primaryTextColor,
    }]];
    label.attributedText = text;
    [card addSubview:label];
    label.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [label.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:15.5],
        [label.centerYAnchor constraintEqualToAnchor:card.centerYAnchor],
    ]];
    return card;
}

- (void)buildOptionCards {
    self.optionCards = [NSMutableArray array];
    NSUInteger count = [self optionRowCount];
    for (NSUInteger i = 0; i < count; i++) {
        [self.optionCards addObject:[self buildOptionCardAtIndex:i]];
    }
}

- (void)buildContinueCta {
    CGSize canvasDesign = [self canvasDesignSize];
    CGRect frame = [self ctaDesignFrame];

    self.ctaBackgroundView = [[UIView alloc] initWithFrame:CGRectZero];
    self.ctaBackgroundView.userInteractionEnabled = YES;
    self.ctaBackgroundView.backgroundColor = [UIColor colorWithRed:205/255.0 green:204/255.0 blue:206/255.0 alpha:1];
    self.ctaBackgroundView.layer.cornerRadius = kCtaCornerRadius;
    self.ctaBackgroundView.layer.masksToBounds = YES;
    self.ctaBackgroundView.accessibilityIdentifier = @"purposeSelection.continue";
    [self.canvasView addSubview:self.ctaBackgroundView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.ctaBackgroundView
                                                                      parent:self.canvasView
                                                                 designFrame:frame
                                                            parentDesignSize:canvasDesign]];

    self.ctaLabel = [[UILabel alloc] init];
    self.ctaLabel.text = @"Continue";
    self.ctaLabel.font = [self ctaFont];
    self.ctaLabel.textColor = PurposeSelectionStyle.onCtaTextColor;
    self.ctaLabel.textAlignment = NSTextAlignmentCenter;
    self.ctaLabel.userInteractionEnabled = NO;
    self.ctaLabel.accessibilityIdentifier = @"purposeSelection.continueLabel";
    [self.ctaBackgroundView addSubview:self.ctaLabel];
    self.ctaLabel.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.ctaLabel.centerXAnchor constraintEqualToAnchor:self.ctaBackgroundView.centerXAnchor],
        [self.ctaLabel.centerYAnchor constraintEqualToAnchor:self.ctaBackgroundView.centerYAnchor],
    ]];
}

#pragma mark - Interactions

- (void)connectInteractions {
    [self.optionCards enumerateObjectsUsingBlock:^(UIView *card, NSUInteger idx, BOOL *stop) {
        UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapOption:)];
        [card addGestureRecognizer:tap];
    }];

    UITapGestureRecognizer *backTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapBack:)];
    [self.navBackView addGestureRecognizer:backTap];

    UITapGestureRecognizer *skipTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapSkip:)];
    [self.skipLabel addGestureRecognizer:skipTap];

    UITapGestureRecognizer *ctaTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapContinue:)];
    [self.ctaBackgroundView addGestureRecognizer:ctaTap];
}

#pragma mark - Actions

- (void)didTapOption:(UITapGestureRecognizer *)recognizer {
    NSUInteger idx = [self.optionCards indexOfObject:recognizer.view];
    if (idx == NSNotFound) return;
    const PurposeOptionRow *rows = [self optionRows];
    NSLog(@"IHEREFOR_EVENT didTapPurposeOption index=%lu label=%@", (unsigned long)idx, rows[idx].label);
}

- (void)didTapBack:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapBack");
}

- (void)didTapSkip:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapSkip");
}

- (void)didTapContinue:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapContinue");
}

#pragma mark - Evidence

- (void)logRegionFrames {
    for (UIView *subview in self.canvasView.subviews) {
        if (!subview.accessibilityIdentifier.length) continue;
        CGRect frameInRoot = [subview convertRect:subview.bounds toView:self.view];
        NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ class=%@ frame=%.3f,%.3f,%.3f,%.3f",
              subview.accessibilityIdentifier, NSStringFromClass(subview.class),
              frameInRoot.origin.x, frameInRoot.origin.y, frameInRoot.size.width, frameInRoot.size.height);
    }
    for (UIView *subview in self.ctaBackgroundView.subviews) {
        if (!subview.accessibilityIdentifier.length) continue;
        CGRect frameInRoot = [subview convertRect:subview.bounds toView:self.view];
        NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ class=%@ frame=%.3f,%.3f,%.3f,%.3f",
              subview.accessibilityIdentifier, NSStringFromClass(subview.class),
              frameInRoot.origin.x, frameInRoot.origin.y, frameInRoot.size.width, frameInRoot.size.height);
    }
}

@end
