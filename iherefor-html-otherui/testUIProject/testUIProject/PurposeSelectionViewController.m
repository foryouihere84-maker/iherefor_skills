//
//  PurposeSelectionViewController.m
//  testUIProject
//
//  Purpose-selection onboarding screen (Lanhu image_id cc79645f + 目的-iPad 28d3d7b5).
//
//  Layout contract: the Lanhu canvas is a fixed board mapped onto the window with
//  the `fit` policy (one uniform scale, centred). Every region anchors to its direct
//  parent through PurposeSelectionStyle's proportional closure — positions are
//  design-frame ratios, control sizes (font sizes, corners, borders, emoji width)
//  stay at their literal design values.
//
//  Two-device adaptation: the design exists as TWO Lanhu boards — "目的" (phone,
//  393x852, image_id cc79645f) and "目的-iPad" (tablet, 810x1080, image_id
//  28d3d7b5). They are the same content laid out at two widths, but the iPad board
//  is NOT a uniform scale-up: card width goes 353→481 (height stays 66), the CTA
//  grows 347x56→480x75, the hero grows 365→396 tall, and the card VERTICAL ORDER
//  differs. So this view switches between two full layout specs on
//  `horizontalSizeClass`: compact → phone spec, regular → iPad spec. Each spec is
//  expressed against its own canvas (see ../../.ihereforUI/pages/purpose/runs/*/
//  ui-implementation-plan.json -> adaptiveLayout.sizeVariants), so both stay
//  "照稿还原" (faithful to their own board) — not a scale-up.
//
//  Data gap (recorded, not silently papered over): the "目的-iPad" design_document
//  is MISSING the text layers for two cards — "🖊️ Develop my coloring skills"
//  (card frame at y=200) and "🎨 Express my creativity" (card frame at y=276).
//  Their card frames exist (6 card frames total at y=124/162/200/238/276/314) but
//  the typography node is absent, almost certainly an export omission. The phone
//  board has all 6 labels, so the iPad spec reuses the phone labels while taking
//  its geometry from the iPad board (card frames + positions). This is the
//  documented recovery, not a guess at new content.
//
//  System-bars policy (underlap): the HTML paints its hero artwork from y=0 with no
//  safe-area inset. The design's own mock status bar is a placeholder and is not
//  implemented — see ui-implementation-plan.json -> unsupported.
//

#import "PurposeSelectionViewController.h"
#import "PurposeSelectionStyle.h"

static NSString *const kAssetHeroBackground = @"age_hero_background"; // same art as age/brush (md5 identical)
static NSString *const kAssetNavBack = @"age_nav_back";

static const CGFloat kCardCornerRadius = 12.0;
static const CGFloat kCardBorderWidth = 1.5;
static const CGFloat kProgressCornerRadius = 3.0;
static const CGFloat kCtaCornerRadius = 28.0;

/// One option row: emoji + label + design frame (canvas space of the chosen board).
typedef struct {
    __unsafe_unretained NSString *emoji;
    __unsafe_unretained NSString *label;
    CGFloat y;
    CGFloat height;
    CGFloat width;
} PurposeOptionRow;

/// Phone board (393x852). Order follows the phone HTML render: Express (overhangs
/// box_6 top via top:-7), Relax, Have fun, Disconnect, Develop, Other.
static const PurposeOptionRow kPhoneOptionRows[] = {
    {@"🎨", @"Express\u00A0my\u00A0creativity",           358.0, 66.0, 353.0},
    {@"🌸", @"Relax\u00A0myself",                          206.0, 65.0, 353.0},
    {@"😜", @"Have\u00A0fun",                              281.0, 65.0, 353.0},
    {@"🧠", @"Disconnect\u00A0my\u00A0brain",              434.0, 65.0, 353.0},
    {@"🖊️", @"Develop\u00A0my\u00A0coloring\u00A0skills",   509.0, 65.0, 353.0},
    {@"👀", @"Other",                                      584.0, 65.0, 353.0},
};
static const NSUInteger kPhoneOptionRowCount = sizeof(kPhoneOptionRows) / sizeof(kPhoneOptionRows[0]);

/// iPad board (810x1080). Order follows the iPad board's card frames (y=124..314).
/// Card width 481 (not 353) and the vertical order differs from the phone spec — a
/// faithful reproduction of the iPad board, not a scale-up.
static const PurposeOptionRow kIpadOptionRows[] = {
    {@"🌸", @"Relax\u00A0myself",                          124.0, 66.0, 481.0},
    {@"😜", @"Have\u00A0fun",                              162.0, 66.0, 481.0},
    {@"🖊️", @"Develop\u00A0my\u00A0coloring\u00A0skills",   200.0, 66.0, 481.0},
    {@"🧠", @"Disconnect\u00A0my\u00A0brain",              238.0, 66.0, 481.0},
    {@"🎨", @"Express\u00A0my\u00A0creativity",            276.0, 66.0, 481.0},
    {@"👀", @"Other",                                      314.0, 66.0, 481.0},
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
    // phone hero = 365 (index.css section_1); iPad hero = 396 (board's bg frame).
    return self.isRegularWidth ? 396.0 : 365.0;
}

/// Design frame of the Continue pill, in the current board's canvas space.
- (CGRect)ctaDesignFrame {
    // phone: index.css .text-wrapper_7 = 347x56 at (26,725) → but the flat resolved
    // colour pill is (26,725,347,56). iPad board: 480x75 at (82.5,452).
    return self.isRegularWidth
        ? CGRectMake(82.5, 452.0, 480.0, 75.0)
        : CGRectMake(26.0, 725.0, 347.0, 56.0);
}

- (CGRect)titleDesignFrame {
    // phone: (68,108,258,29). iPad: headline sits at the same visual rhythm; board
    // places "How can we help you?" centred-left under the hero. Use board geometry
    // — iPad headline label frame measured from the board text node.
    return self.isRegularWidth
        ? CGRectMake(147.0, 108.0, 415.0, 29.0)
        : CGRectMake(68.0, 108.0, 258.0, 29.0);
}

- (CGRect)skipDesignFrame {
    return self.isRegularWidth
        ? CGRectMake(367.5, 31.0, 35.0, 22.0)
        : CGRectMake(346.0, 60.0, 27.0, 24.0);
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
        // Size class flipping (iPhone↔iPad full screen, split view) changes which
        // board to reproduce. Rebuild the regions against the new canvas.
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

    // hero (0,0,W,heroHeight)
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
    BOOL regular = self.isRegularWidth;

    self.navBackView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetNavBack]];
    self.navBackView.contentMode = UIViewContentModeScaleToFill;
    self.navBackView.userInteractionEnabled = YES;
    self.navBackView.accessibilityIdentifier = @"purposeSelection.back";
    [self.canvasView addSubview:self.navBackView];
    [NSLayoutConstraint activateConstraints:[PurposeSelectionStyle closeChild:self.navBackView
                                                                      parent:self.canvasView
                                                                 designFrame:CGRectMake(regular ? 40.0 : 12.0, regular ? 43.0 : 52.0, 32, 32)
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
                                                                 designFrame:CGRectMake(regular ? 92.0 : 81.0, regular ? 57.0 : 65.0, regular ? 504.0 : 232.0, 6)
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
        [self.progressFillView.widthAnchor constraintEqualToConstant:regular ? 32.0 : 24.0],
    ]];

    self.skipLabel = [[UILabel alloc] init];
    self.skipLabel.text = @"Skip";
    self.skipLabel.font = PurposeSelectionStyle.skipFont;
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
    self.titleLabel.font = PurposeSelectionStyle.headlineFont;
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

/// Build one option card: a white rounded card holding "emoji + text". Size and
/// position come from the current board's spec (phone 353-wide vs iPad 481-wide),
/// so a card's literal geometry follows its own board, not a scale-up.
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
                                                                 designFrame:CGRectMake(self.isRegularWidth ? 82.5 : 20.0, row.y, row.width, row.height)
                                                            parentDesignSize:canvasDesign]];

    UILabel *label = [[UILabel alloc] init];
    label.numberOfLines = 1;
    label.userInteractionEnabled = NO;
    NSMutableAttributedString *text = [[NSMutableAttributedString alloc] init];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:row.emoji
                                                                 attributes:@{
        NSFontAttributeName: [UIFont systemFontOfSize:18.0],
        NSForegroundColorAttributeName: PurposeSelectionStyle.primaryTextColor,
    }]];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:@"\u00A0"
                                                                 attributes:@{
        NSFontAttributeName: PurposeSelectionStyle.optionFont,
        NSForegroundColorAttributeName: PurposeSelectionStyle.primaryTextColor,
    }]];
    [text appendAttributedString:[[NSAttributedString alloc] initWithString:row.label
                                                                 attributes:@{
        NSFontAttributeName: PurposeSelectionStyle.optionFont,
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

    // index.css paints the pill via a 16%-alpha black plate over the page colour,
    // which the browser resolves to flat rgb(205,204,206). Paint that flat colour
    // directly — no image, no alpha compositing.
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
    self.ctaLabel.font = PurposeSelectionStyle.ctaFont;
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
    // TODO: connect business action - record the chosen purpose.
}

- (void)didTapBack:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapBack");
    // TODO: connect business action - pop or dismiss the onboarding flow.
}

- (void)didTapSkip:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapSkip");
    // TODO: connect business action - skip the purpose step.
}

- (void)didTapContinue:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapContinue");
    // TODO: connect business action - advance with the chosen purpose.
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
