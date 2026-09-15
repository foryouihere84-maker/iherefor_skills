//
//  AgeSelectionViewController.m
//  testUIProject
//
//  Age-selection onboarding screen (Lanhu image_id daa18fa7-31ee-400a-bbad-fbfebd5a30e0).
//
//  Layout contract: the Lanhu canvas is a fixed 393x852 board closed onto the window
//  with the `fit` policy (one uniform scale, centred; see ui-implementation-plan.json
//  -> canvasTransform). Every region and inner element anchors to its direct parent
//  through AgeSelectionStyle's proportional closure — positions are expressed as
//  design-frame ratios, control sizes (fonts, radii, borders, emoji width, hit areas)
//  stay at their literal design values. No region hand-tunes its own ratio.
//
//  System-bars policy (systemBars.policy = underlap): the HTML paints its background
//  and hero artwork from y=0 with no safe-area inset, so the page extends under the
//  status bar exactly as in the browser baseline.
//

#import "AgeSelectionViewController.h"
#import "AgeOptionCardView.h"
#import "AgeSelectionStyle.h"

/// Asset names (Lanhu img_* -> semantic).
static NSString *const kAssetHeroBackground = @"age_hero_background";
static NSString *const kAssetCtaBackground = @"age_cta_background";
static NSString *const kAssetNavBack = @"age_nav_back";

/// The first step fills 24pt of the 232pt progress track (index.css `.group_1`).
static const CGFloat kProgressFillDesignWidth = 24.0;

@interface AgeSelectionViewController ()
@property(nonatomic, strong) UIView *canvasView;
@property(nonatomic, strong) UIImageView *heroBackgroundView;
@property(nonatomic, strong) UIImageView *navBackView;
@property(nonatomic, strong) UIView *progressTrackView;
@property(nonatomic, strong) UIView *progressFillView;
@property(nonatomic, strong) UILabel *skipLabel;
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UIImageView *ctaBackgroundView;
@property(nonatomic, strong) UILabel *ctaLabel;
@property(nonatomic, copy) NSArray<AgeOptionCardView *> *optionCards;
@property(nonatomic, assign) NSInteger selectedIndex;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@end

@implementation AgeSelectionViewController

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];

    self.view.backgroundColor = AgeSelectionStyle.pageBackgroundColor; // baseline-viewport.css sets body bg to page colour, so the letterbox bands match
    self.view.accessibilityIdentifier = @"age-selection";
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;
    self.selectedIndex = 0; // "Less than 14" is the default selected card.

    NSLog(@"IHEREFOR_RUNTIME_SCREEN_BOUNDS width=%.4f height=%.4f scale=%.4f nativeScale=%.4f",
          UIScreen.mainScreen.bounds.size.width, UIScreen.mainScreen.bounds.size.height,
          UIScreen.mainScreen.scale, UIScreen.mainScreen.nativeScale);

    [self buildRegions];
}

- (UIStatusBarStyle)preferredStatusBarStyle {
    return UIStatusBarStyleDarkContent;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];

    UIEdgeInsets insets = self.view.safeAreaInsets;
    CGSize viewSize = self.view.bounds.size;
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f safeTop=%.4f safeBottom=%.4f "
          @"canvasDesignW=%.4f canvasDesignH=%.4f uniformScale=%.8f policy=fit",
          viewSize.width, viewSize.height, insets.top, insets.bottom,
          kAgeSelectionCanvasWidth, kAgeSelectionCanvasHeight,
          viewSize.width / kAgeSelectionCanvasWidth);

    [self logRegionFrames];
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY page=age-selection");
    [AgeSelectionStyle logClosureCounters];
    [self logRegionFrames];
}

#pragma mark - Region assembly

- (void)buildRegions {
    if (self.hasBuiltRegions) {
        return;
    }
    self.hasBuiltRegions = YES;

    // --- root canvas (fit: width-to-window, height by 852/393 aspect) ---
    self.canvasView = [[UIView alloc] initWithFrame:CGRectZero];
    self.canvasView.backgroundColor = AgeSelectionStyle.pageBackgroundColor;
    self.canvasView.clipsToBounds = YES;
    self.canvasView.accessibilityIdentifier = @"ageSelection.canvas";
    [self.view addSubview:self.canvasView];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle fitCanvas:self.canvasView
                                                             insideView:self.view]];

    // --- hero background (0,0,393,365) ---
    self.heroBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetHeroBackground]];
    self.heroBackgroundView.contentMode = UIViewContentModeScaleToFill;
    self.heroBackgroundView.accessibilityIdentifier = @"ageSelection.hero";
    [self.canvasView addSubview:self.heroBackgroundView];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.heroBackgroundView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(0, 0, kAgeSelectionCanvasWidth, 365)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)]];

    // --- navigation row (back + progress + skip) ---
    [self buildNavRow];
    // --- title ---
    [self buildTitle];
    // --- six age option cards ---
    [self buildAgeCards];
    // --- continue CTA ---
    [self buildContinueCta];

    [self connectInteractions];
    [self refreshSelection];
}

- (void)buildNavRow {
    self.navBackView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetNavBack]];
    self.navBackView.contentMode = UIViewContentModeScaleToFill;
    self.navBackView.userInteractionEnabled = YES;
    self.navBackView.accessibilityIdentifier = @"ageSelection.back";
    [self.canvasView addSubview:self.navBackView];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.navBackView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(12, 52, 32, 32)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)
                                                                 sizeMode:AgeSelectionClosureSizeIntrinsic
                                                                   anchor:AgeSelectionClosureAnchorLeading]];

    // Progress track (81,65,232,6) with a 24pt-ready fill.
    self.progressTrackView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressTrackView.backgroundColor = AgeSelectionStyle.progressTrackColor;
    self.progressTrackView.layer.cornerRadius = 3.0;
    self.progressTrackView.layer.masksToBounds = YES;
    self.progressTrackView.accessibilityIdentifier = @"ageSelection.progressTrack";
    [self.canvasView addSubview:self.progressTrackView];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.progressTrackView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(81, 65, 232, 6)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)]];

    self.progressFillView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressFillView.backgroundColor = AgeSelectionStyle.progressFillColor;
    self.progressFillView.layer.cornerRadius = 3.0;
    self.progressFillView.layer.masksToBounds = YES;
    self.progressFillView.accessibilityIdentifier = @"ageSelection.progressFill";
    [self.progressTrackView addSubview:self.progressFillView];
    self.progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.progressFillView.leadingAnchor constraintEqualToAnchor:self.progressTrackView.leadingAnchor],
        [self.progressFillView.topAnchor constraintEqualToAnchor:self.progressTrackView.topAnchor],
        [self.progressFillView.bottomAnchor constraintEqualToAnchor:self.progressTrackView.bottomAnchor],
        [self.progressFillView.widthAnchor constraintEqualToConstant:kProgressFillDesignWidth],
    ]];

    self.skipLabel = [[UILabel alloc] init];
    self.skipLabel.text = @"Skip";
    self.skipLabel.font = AgeSelectionStyle.skipFont;
    self.skipLabel.textColor = AgeSelectionStyle.skipTextColor;
    self.skipLabel.textAlignment = NSTextAlignmentLeft;
    self.skipLabel.userInteractionEnabled = YES;
    self.skipLabel.accessibilityIdentifier = @"ageSelection.skip";
    [self.canvasView addSubview:self.skipLabel];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.skipLabel
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(346, 60, 27, 24)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)
                                                                 sizeMode:AgeSelectionClosureSizeIntrinsic
                                                                   anchor:AgeSelectionClosureAnchorLeading]];
}

- (void)buildTitle {
    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.text = @"What’s your age?";
    self.titleLabel.font = AgeSelectionStyle.headlineFont;
    self.titleLabel.textColor = AgeSelectionStyle.primaryTextColor;
    self.titleLabel.textAlignment = NSTextAlignmentLeft;
    self.titleLabel.accessibilityIdentifier = @"ageSelection.title";
    [self.canvasView addSubview:self.titleLabel];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.titleLabel
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(97, 108, 200, 29)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)
                                                                 sizeMode:AgeSelectionClosureSizeIntrinsic
                                                                   anchor:AgeSelectionClosureAnchorLeading]];
}

- (void)buildAgeCards {
    // Six cards in reading order: less-than-14, 14-17, 18-24, 25-34, 35-44, 45-or-older.
    // Design frames (x=20, width 353, height 65/66): y = 206, 281, 358, 434, 509, 584.
    NSArray<NSArray<NSString *> *> *specs = @[
        @[@"✏️", @"Less than 14"],
        @[@"🎓", @"14-17"],
        @[@"🖌️", @"18-24"],
        @[@"💼", @"25-34"],
        @[@"🌟", @"35-44"],
        @[@"🌵", @"45 or older"],
    ];
    NSArray<NSNumber *> *yValues = @[@206.0, @281.0, @358.0, @434.0, @509.0, @584.0];
    NSArray<NSNumber *> *heights = @[@65.0, @65.0, @66.0, @65.0, @65.0, @65.0];

    NSMutableArray<AgeOptionCardView *> *cards = [NSMutableArray array];
    for (NSUInteger i = 0; i < specs.count; i++) {
        AgeOptionCardView *card = [[AgeOptionCardView alloc] initWithEmoji:specs[i][0] label:specs[i][1]];
        card.accessibilityIdentifier = [NSString stringWithFormat:@"ageSelection.card%lu", (unsigned long)i];
        [self.canvasView addSubview:card];
        [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:card
                                                                       parent:self.canvasView
                                                                  designFrame:CGRectMake(20,
                                                                                         yValues[i].doubleValue,
                                                                                         353,
                                                                                         heights[i].doubleValue)
                                                             parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                          kAgeSelectionCanvasHeight)]];
        [cards addObject:card];
    }
    self.optionCards = cards;
}

- (void)buildContinueCta {
    self.ctaBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetCtaBackground]];
    self.ctaBackgroundView.contentMode = UIViewContentModeScaleToFill;
    self.ctaBackgroundView.userInteractionEnabled = YES;
    self.ctaBackgroundView.accessibilityIdentifier = @"ageSelection.continue";
    [self.canvasView addSubview:self.ctaBackgroundView];
    [NSLayoutConstraint activateConstraints:[AgeSelectionStyle closeChild:self.ctaBackgroundView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(26, 725, 347, 56)
                                                         parentDesignSize:CGSizeMake(kAgeSelectionCanvasWidth,
                                                                                      kAgeSelectionCanvasHeight)]];

    self.ctaLabel = [[UILabel alloc] init];
    self.ctaLabel.text = @"Continue";
    self.ctaLabel.font = AgeSelectionStyle.ctaFont;
    self.ctaLabel.textColor = AgeSelectionStyle.onCtaTextColor;
    self.ctaLabel.textAlignment = NSTextAlignmentCenter;
    self.ctaLabel.userInteractionEnabled = NO;
    self.ctaLabel.accessibilityIdentifier = @"ageSelection.continueLabel";
    [self.ctaBackgroundView addSubview:self.ctaLabel];
    self.ctaLabel.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.ctaLabel.centerXAnchor constraintEqualToAnchor:self.ctaBackgroundView.centerXAnchor],
        [self.ctaLabel.centerYAnchor constraintEqualToAnchor:self.ctaBackgroundView.centerYAnchor],
    ]];
}

#pragma mark - Interactions

- (void)connectInteractions {
    [self.optionCards enumerateObjectsUsingBlock:^(AgeOptionCardView *card, NSUInteger idx, BOOL *stop) {
        __weak typeof(self) weakSelf = self;
        card.onTap = ^(AgeOptionCardView *tapped) {
            __strong typeof(weakSelf) strongSelf = weakSelf;
            if (!strongSelf) return;
            [strongSelf didTapAgeOption:tapped];
        };
    }];

    UITapGestureRecognizer *backTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapBack:)];
    [self.navBackView addGestureRecognizer:backTap];

    UITapGestureRecognizer *skipTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapSkip:)];
    [self.skipLabel addGestureRecognizer:skipTap];

    UITapGestureRecognizer *ctaTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapContinue:)];
    [self.ctaBackgroundView addGestureRecognizer:ctaTap];
}

- (void)refreshSelection {
    [self.optionCards enumerateObjectsUsingBlock:^(AgeOptionCardView *card, NSUInteger idx, BOOL *stop) {
        card.selectedState = (idx == (NSUInteger)self.selectedIndex);
    }];
}

#pragma mark - Actions

- (void)didTapAgeOption:(AgeOptionCardView *)card {
    NSUInteger idx = [self.optionCards indexOfObject:card];
    if (idx == NSNotFound) return;
    self.selectedIndex = (NSInteger)idx;
    [self refreshSelection];
    NSLog(@"IHEREFOR_EVENT didTapAgeOption index=%lu label=%@", (unsigned long)idx, card.optionLabel);
    // TODO: connect business action - forward the selected age band.
}

- (void)didTapBack:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapBack");
    // TODO: connect business action - pop or dismiss the onboarding flow.
}

- (void)didTapSkip:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapSkip");
    // TODO: connect business action - skip the age step.
}

- (void)didTapContinue:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapContinue selectedIndex=%ld", (long)self.selectedIndex);
    // TODO: connect business action - advance with the selected age band.
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
