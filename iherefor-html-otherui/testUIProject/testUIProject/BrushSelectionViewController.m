//
//  BrushSelectionViewController.m
//  testUIProject
//
//  Brush-selection onboarding screen (Lanhu image_id cf7f9412-93ae-4081-ac78-ce4863faa1e7).
//
//  Layout contract: the Lanhu canvas is a fixed 393x852 board closed onto the window
//  with the `fit` policy (one uniform scale, centred; see ui-implementation-plan.json
//  -> canvasTransform). Every region and inner element anchors to its direct parent
//  through BrushSelectionStyle's proportional closure — positions are expressed as
//  design-frame ratios, control sizes (font sizes, the 32pt icon, text advance
//  widths, corner radii, border widths, hit areas) stay at their literal design
//  values. No region hand-tunes its own ratio.
//
//  Stacking order (index.css paints the same way, in DOM order):
//    hero wash -> nav row -> headline -> 7 option cards -> bottom scrim -> CTA.
//  The scrim is a real alpha gradient (img_15 is transparent at its top edge and
//  fully opaque from ~100pt down), so the cards genuinely fade out under it.
//
//  System-bars policy (systemBars.policy = underlap): the HTML paints its background
//  and hero artwork from y=0 with no safe-area inset, so the page extends under the
//  status bar exactly as in the browser baseline. The design's own mock status bar
//  (9:41 + signal/WiFi/battery bitmaps at y=14~34) is a design-time placeholder and
//  is deliberately not implemented — see ui-implementation-plan.json -> unsupported.
//

#import "BrushSelectionViewController.h"
#import "BrushOptionCardView.h"
#import "BrushSelectionStyle.h"

#pragma mark - Asset names (Lanhu img_* -> semantic)

static NSString *const kAssetHeroBackground = @"brush_hero_background";
static NSString *const kAssetNavBack = @"brush_nav_back";
static NSString *const kAssetBottomScrim = @"brush_bottom_scrim";
static NSString *const kAssetCtaBackground = @"brush_cta_background";
static NSString *const kAssetCardPaintBrush = @"brush_option_paint_brush_art";
static NSString *const kAssetCardPencil = @"brush_option_pencil_art";
static NSString *const kAssetCardWatercolor = @"brush_option_watercolor_art";
static NSString *const kAssetCardPastel = @"brush_option_pastel_art";
static NSString *const kAssetCardSprayPaint = @"brush_option_spray_paint_art";
static NSString *const kAssetCardMarker = @"brush_option_marker_art";
static NSString *const kAssetCardFlatBrush = @"brush_option_flat_brush_art";
static NSString *const kAssetPastelSmear = @"brush_option_pastel_smear_art";
static NSString *const kAssetPastelSmearInner = @"brush_option_pastel_smear_inner_art";
static NSString *const kAssetPastelSmearTip = @"brush_option_pastel_smear_tip_art";

#pragma mark - Design constants (index.css; never scaled)

static const CGFloat kBrushCardDesignWidth = 353.0;
static const CGFloat kBrushHeadlineLineHeight = 29.0;  ///< `.paragraph_1 { line-height: 29px }`
static const CGFloat kBrushSkipLineHeight = 17.0;      ///< `.text_3 { line-height: 17px }`
static const CGFloat kBrushCtaLineHeight = 22.0;       ///< `.text_10 { line-height: 22px }`
static const CGFloat kBrushProgressCornerRadius = 3.0; ///< `.group_3/.group_4 { border-radius: 3px }`
static const CGFloat kBrushCtaCornerRadius = 28.0;     ///< `.text-wrapper_8 { border-radius: 28px }`

/// One row of the option list: design y, design height, art natural height, ring.
typedef struct {
    __unsafe_unretained NSString *title;
    __unsafe_unretained NSString *art;
    CGFloat y;
    CGFloat height;
    CGFloat artHeight;
    BOOL bordered;
} BrushOptionRow;

static const BrushOptionRow kBrushOptionRows[] = {
    // y = 206 + 97*i while the cards stay 87 tall with a 10pt gap; the Pastel and
    // Marker cards are 85 tall (their art is 86 and gets clipped by `overflow:
    // hidden`), and the borderless Flat Brush card is 70 tall — it sits entirely
    // under the opaque part of the scrim.
    {@"Paint Brush", kAssetCardPaintBrush, 206.0, 87.0, 86.0, YES},
    {@"Pencil",      kAssetCardPencil,     303.0, 87.0, 86.0, YES},
    {@"Watercolor",  kAssetCardWatercolor, 398.0, 87.0, 86.0, YES},
    {@"Pastel",      kAssetCardPastel,     495.0, 85.0, 86.0, YES},
    {@"Spray Paint", kAssetCardSprayPaint, 590.0, 87.0, 86.0, YES},
    {@"Marker",      kAssetCardMarker,     687.0, 85.0, 86.0, YES},
    {@"Flat Brush",  kAssetCardFlatBrush,  782.0, 70.0, 70.0, NO},
};
static const NSUInteger kBrushOptionRowCount = sizeof(kBrushOptionRows) / sizeof(kBrushOptionRows[0]);

@interface BrushSelectionViewController ()
@property(nonatomic, strong) UIView *canvasView;
@property(nonatomic, strong) UIImageView *heroBackgroundView;
@property(nonatomic, strong) UIImageView *navBackView;
@property(nonatomic, strong) UIView *progressTrackView;
@property(nonatomic, strong) UIView *progressFillView;
@property(nonatomic, strong) UILabel *skipLabel;
@property(nonatomic, strong) UILabel *headlineLabel;
@property(nonatomic, strong) UIImageView *bottomScrimView;
@property(nonatomic, strong) UIImageView *ctaBackgroundView;
@property(nonatomic, strong) UILabel *ctaLabel;
@property(nonatomic, copy) NSArray<BrushOptionCardView *> *optionCards;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@end

@implementation BrushSelectionViewController

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];

    // baseline-viewport.css paints `html, body` with the page colour, so the
    // letterbox bands above/below the fitted canvas match the design.
    self.view.backgroundColor = BrushSelectionStyle.pageBackgroundColor;
    self.view.accessibilityIdentifier = @"brush-selection";
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

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];

    UIEdgeInsets insets = self.view.safeAreaInsets;
    CGSize viewSize = self.view.bounds.size;
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f safeTop=%.4f safeBottom=%.4f "
          @"canvasDesignW=%.4f canvasDesignH=%.4f uniformScale=%.8f policy=fit",
          viewSize.width, viewSize.height, insets.top, insets.bottom,
          kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight,
          viewSize.width / kBrushSelectionCanvasWidth);

    [self logRegionFrames];
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY page=brush-selection");
    [BrushSelectionStyle logClosureCounters];
    [self logRegionFrames];
}

#pragma mark - Region assembly

- (void)buildRegions {
    if (self.hasBuiltRegions) {
        return;
    }
    self.hasBuiltRegions = YES;

    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);

    // --- root canvas (fit: width-to-window, height by 852/393 aspect) ---
    self.canvasView = [[UIView alloc] initWithFrame:CGRectZero];
    self.canvasView.backgroundColor = BrushSelectionStyle.pageBackgroundColor;
    self.canvasView.clipsToBounds = YES;
    self.canvasView.accessibilityIdentifier = @"brushSelection.canvas";
    [self.view addSubview:self.canvasView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle fitCanvas:self.canvasView
                                                               insideView:self.view]];

    // --- hero wash (0,0,393,365) ---
    self.heroBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetHeroBackground]];
    self.heroBackgroundView.contentMode = UIViewContentModeScaleToFill;
    self.heroBackgroundView.accessibilityIdentifier = @"brushSelection.hero";
    [self.canvasView addSubview:self.heroBackgroundView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.heroBackgroundView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(0, 0, canvasDesign.width, 365)
                                                         parentDesignSize:canvasDesign]];

    [self buildNavRow];
    [self buildHeadline];
    [self buildOptionCards];
    [self buildBottomScrim];
    [self buildContinueCta];

    [self connectInteractions];
}

- (void)buildNavRow {
    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);

    // Back icon (12,52,32,32) — img_3 is exactly 32x32, so intrinsic sizing keeps
    // the tap target at its design size.
    self.navBackView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetNavBack]];
    self.navBackView.contentMode = UIViewContentModeScaleToFill;
    self.navBackView.userInteractionEnabled = YES;
    self.navBackView.accessibilityIdentifier = @"brushSelection.back";
    [self.canvasView addSubview:self.navBackView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.navBackView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(12, 52, 32, 32)
                                                         parentDesignSize:canvasDesign
                                                                 sizeMode:BrushSelectionClosureSizeIntrinsic
                                                                   anchor:BrushSelectionClosureAnchorLeading]];

    // Progress track (81,65,232,6). index.css `.group_4` is `width: 232px` — the
    // same width as the track itself — and the baseline row at y=68 is solid
    // rgb(22,22,22) from x=81 to x=313, so the fill is full width here.
    self.progressTrackView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressTrackView.backgroundColor = BrushSelectionStyle.progressTrackColor;
    self.progressTrackView.layer.cornerRadius = kBrushProgressCornerRadius;
    self.progressTrackView.layer.masksToBounds = YES;
    self.progressTrackView.accessibilityIdentifier = @"brushSelection.progressTrack";
    [self.canvasView addSubview:self.progressTrackView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.progressTrackView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(81, 65, 232, 6)
                                                         parentDesignSize:canvasDesign]];

    self.progressFillView = [[UIView alloc] initWithFrame:CGRectZero];
    self.progressFillView.backgroundColor = BrushSelectionStyle.progressFillColor;
    self.progressFillView.layer.cornerRadius = kBrushProgressCornerRadius;
    self.progressFillView.layer.masksToBounds = YES;
    self.progressFillView.accessibilityIdentifier = @"brushSelection.progressFill";
    [self.progressTrackView addSubview:self.progressFillView];
    self.progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.progressFillView.leadingAnchor constraintEqualToAnchor:self.progressTrackView.leadingAnchor],
        [self.progressFillView.trailingAnchor constraintEqualToAnchor:self.progressTrackView.trailingAnchor],
        [self.progressFillView.topAnchor constraintEqualToAnchor:self.progressTrackView.topAnchor],
        [self.progressFillView.bottomAnchor constraintEqualToAnchor:self.progressTrackView.bottomAnchor],
    ]];

    // Skip (346,60,27,17). index.css stretches the flex item to 24pt tall but the
    // line box itself is only `line-height: 17px`, so the text is anchored at the
    // design top and the extra 7pt of empty box is not reproduced.
    self.skipLabel = [[UILabel alloc] init];
    NSMutableParagraphStyle *skipStyle =
        [[BrushSelectionStyle paragraphStyleWithLineHeight:kBrushSkipLineHeight] mutableCopy];
    skipStyle.lineBreakMode = NSLineBreakByClipping;
    self.skipLabel.attributedText = [[NSAttributedString alloc] initWithString:@"Skip"
                                                                   attributes:@{
        NSFontAttributeName: BrushSelectionStyle.skipFont,
        NSForegroundColorAttributeName: BrushSelectionStyle.skipTextColor,
        NSParagraphStyleAttributeName: skipStyle,
    }];
    self.skipLabel.numberOfLines = 1;
    self.skipLabel.textAlignment = NSTextAlignmentLeft;
    self.skipLabel.userInteractionEnabled = YES;
    self.skipLabel.accessibilityIdentifier = @"brushSelection.skip";
    [self.canvasView addSubview:self.skipLabel];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.skipLabel
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(346, 60, 0, 0)
                                                         parentDesignSize:canvasDesign
                                                                 sizeMode:BrushSelectionClosureSizeIntrinsic
                                                                   anchor:BrushSelectionClosureAnchorLeading]];
}

- (void)buildHeadline {
    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);

    // `.paragraph_1`: 321 x 58 at (36,108), Avenir-Black 24 / line-height 29,
    // `text-align: right`. The line break is explicit in the export (`<br>`), and
    // the words are joined with `&nbsp;`, so the label reproduces both: a forced
    // newline and non-breaking spaces that cannot wrap.
    NSMutableParagraphStyle *style =
        [[BrushSelectionStyle paragraphStyleWithLineHeight:kBrushHeadlineLineHeight] mutableCopy];
    style.alignment = NSTextAlignmentRight;
    style.lineBreakMode = NSLineBreakByClipping;

    NSString *headline = @"Which\u00A0brushes\u00A0are\u00A0you\u00A0most\nexcited\u00A0to\u00A0try?";

    self.headlineLabel = [[UILabel alloc] init];
    self.headlineLabel.attributedText = [[NSAttributedString alloc] initWithString:headline
                                                                       attributes:@{
        NSFontAttributeName: BrushSelectionStyle.headlineFont,
        NSForegroundColorAttributeName: BrushSelectionStyle.primaryTextColor,
        NSParagraphStyleAttributeName: style,
    }];
    self.headlineLabel.numberOfLines = 2;
    self.headlineLabel.textAlignment = NSTextAlignmentRight;
    self.headlineLabel.accessibilityIdentifier = @"brushSelection.title";
    [self.canvasView addSubview:self.headlineLabel];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.headlineLabel
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(36, 108, 321, 58)
                                                         parentDesignSize:canvasDesign]];
}

- (void)buildOptionCards {
    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);
    NSMutableArray<BrushOptionCardView *> *cards = [NSMutableArray array];

    for (NSUInteger i = 0; i < kBrushOptionRowCount; i++) {
        BrushOptionRow row = kBrushOptionRows[i];
        CGSize cardDesign = CGSizeMake(kBrushCardDesignWidth, row.height);

        NSArray<BrushCardLayerSpec *> *layers = (row.art == kAssetCardPastel)
            ? [self pastelSmearLayersForCardDesign:cardDesign]
            : nil;

        BrushOptionCardView *card =
            [BrushOptionCardView cardWithIdentifier:[NSString stringWithFormat:@"brushSelection.card%lu", (unsigned long)i]
                                              title:row.title
                                           artNamed:row.art
                                         designSize:cardDesign
                                          artHeight:row.artHeight
                                           bordered:row.bordered
                                         layerSpecs:layers];
        [self.canvasView addSubview:card];
        [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:card
                                                                       parent:self.canvasView
                                                                  designFrame:CGRectMake(20, row.y, kBrushCardDesignWidth, row.height)
                                                             parentDesignSize:canvasDesign]];
        [cards addObject:card];
    }
    self.optionCards = cards;
}

/// The Pastel card's green smear is the only composite in the design: the exported
/// DOM nests `.box_4 > .box_5 > .image-wrapper_1 > .image_2`, three layers deep, and
/// each frame below is the one measured in reference/page-facts.json expressed
/// against its own immediate parent.
- (NSArray<BrushCardLayerSpec *> *)pastelSmearLayersForCardDesign:(CGSize)cardDesign {
    BrushCardLayerSpec *smear = [BrushCardLayerSpec layerNamed:kAssetPastelSmear
                                                   designFrame:CGRectMake(197.5, 5.5, 154.5, 80)
                                              parentDesignSize:cardDesign
                                                   parentIndex:NSNotFound];
    BrushCardLayerSpec *inner = [BrushCardLayerSpec layerNamed:kAssetPastelSmearInner
                                                   designFrame:CGRectMake(31, 5, 113.5, 49)
                                              parentDesignSize:CGSizeMake(154.5, 80)
                                                   parentIndex:0];
    // The tip overhangs its parent's top edge by 11pt (`margin: -11px`); the closure
    // supports the negative offset, and the card's `masksToBounds` clips it exactly
    // like `.box_4 { overflow: hidden }` does.
    BrushCardLayerSpec *tip = [BrushCardLayerSpec layerNamed:kAssetPastelSmearTip
                                                 designFrame:CGRectMake(19, -11, 105, 43)
                                            parentDesignSize:CGSizeMake(113.5, 49)
                                                 parentIndex:1];
    return @[smear, inner, tip];
}

- (void)buildBottomScrim {
    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);

    // (0,662,393,190) — an alpha gradient that fades the card list into the page
    // colour. Added after the cards so it genuinely covers them.
    self.bottomScrimView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetBottomScrim]];
    self.bottomScrimView.contentMode = UIViewContentModeScaleToFill;
    self.bottomScrimView.userInteractionEnabled = NO;
    self.bottomScrimView.accessibilityIdentifier = @"brushSelection.scrim";
    [self.canvasView addSubview:self.bottomScrimView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.bottomScrimView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(0, 662, canvasDesign.width, 190)
                                                         parentDesignSize:canvasDesign]];
}

- (void)buildContinueCta {
    CGSize canvasDesign = CGSizeMake(kBrushSelectionCanvasWidth, kBrushSelectionCanvasHeight);

    // (26,728,347,56) — img_16 is the plate with its arrow already baked in.
    self.ctaBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetCtaBackground]];
    self.ctaBackgroundView.contentMode = UIViewContentModeScaleToFill;
    self.ctaBackgroundView.userInteractionEnabled = YES;
    self.ctaBackgroundView.accessibilityIdentifier = @"brushSelection.continue";
    [self.canvasView addSubview:self.ctaBackgroundView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.ctaBackgroundView
                                                                   parent:self.canvasView
                                                              designFrame:CGRectMake(26, 728, 347, 56)
                                                         parentDesignSize:canvasDesign]];

    // `.text-wrapper_8 { padding: 17px 155px 17px 124px }` — the label is pinned at
    // its design left inset, not centred: 124 + 68 + 155 = 347 exactly.
    NSMutableParagraphStyle *style =
        [[BrushSelectionStyle paragraphStyleWithLineHeight:kBrushCtaLineHeight] mutableCopy];
    style.lineBreakMode = NSLineBreakByClipping;

    self.ctaLabel = [[UILabel alloc] init];
    self.ctaLabel.attributedText = [[NSAttributedString alloc] initWithString:@"Continue"
                                                                  attributes:@{
        NSFontAttributeName: BrushSelectionStyle.ctaFont,
        NSForegroundColorAttributeName: BrushSelectionStyle.onCtaTextColor,
        NSParagraphStyleAttributeName: style,
    }];
    self.ctaLabel.numberOfLines = 1;
    self.ctaLabel.textAlignment = NSTextAlignmentLeft;
    self.ctaLabel.userInteractionEnabled = NO;
    self.ctaLabel.accessibilityIdentifier = @"brushSelection.continueLabel";
    [self.ctaBackgroundView addSubview:self.ctaLabel];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.ctaLabel
                                                                   parent:self.ctaBackgroundView
                                                              designFrame:CGRectMake(124, 17, 0, 0)
                                                         parentDesignSize:CGSizeMake(347, 56)
                                                                 sizeMode:BrushSelectionClosureSizeIntrinsic
                                                                   anchor:BrushSelectionClosureAnchorLeading]];
}

#pragma mark - Interactions

- (void)connectInteractions {
    for (BrushOptionCardView *card in self.optionCards) {
        __weak typeof(self) weakSelf = self;
        card.onTap = ^(BrushOptionCardView *tapped) {
            __strong typeof(weakSelf) strongSelf = weakSelf;
            if (!strongSelf) return;
            [strongSelf didTapBrushOption:tapped];
        };
    }

    UITapGestureRecognizer *backTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapBack:)];
    [self.navBackView addGestureRecognizer:backTap];

    UITapGestureRecognizer *skipTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapSkip:)];
    [self.skipLabel addGestureRecognizer:skipTap];

    UITapGestureRecognizer *ctaTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(didTapContinue:)];
    [self.ctaBackgroundView addGestureRecognizer:ctaTap];
}

#pragma mark - Actions

- (void)didTapBrushOption:(BrushOptionCardView *)card {
    NSUInteger idx = [self.optionCards indexOfObject:card];
    if (idx == NSNotFound) return;
    NSLog(@"IHEREFOR_EVENT didTapBrushOption index=%lu label=%@", (unsigned long)idx, card.optionLabel);
    // TODO: connect business action - toggle the brush in the selection set. The
    // design shows no selected state (all seven cards render the same grey ring),
    // so no selected styling is invented here.
}

- (void)didTapBack:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapBack");
    // TODO: connect business action - pop or dismiss the onboarding flow.
}

- (void)didTapSkip:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapSkip");
    // TODO: connect business action - skip the brush step.
}

- (void)didTapContinue:(UITapGestureRecognizer *)recognizer {
    NSLog(@"IHEREFOR_EVENT didTapContinue");
    // TODO: connect business action - advance with the selected brushes.
}

#pragma mark - Evidence

- (void)logRegionFrames {
    [self logSubviewTree:self.canvasView depth:0];
}

- (void)logSubviewTree:(UIView *)view depth:(NSUInteger)depth {
    for (UIView *subview in view.subviews) {
        if (subview.accessibilityIdentifier.length) {
            CGRect frameInRoot = [subview convertRect:subview.bounds toView:self.view];
            NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ depth=%lu frame=%.3f,%.3f,%.3f,%.3f",
                  subview.accessibilityIdentifier, (unsigned long)depth,
                  frameInRoot.origin.x, frameInRoot.origin.y,
                  frameInRoot.size.width, frameInRoot.size.height);
        }
        [self logSubviewTree:subview depth:depth + 1];
    }
}

@end
