//
//  PaletteSelectionViewController.m
//  testUIProject
//
//  Palette-selection onboarding screen (Lanhu "色板" c5e17728-2b7d-4d52-b5a6-3e8a710ec9f6).
//
//  A single phone board (393x852) mapped with the `fit` policy (one uniform scale,
//  centred). The screen shows a header (status bar, back button, progress, skip,
//  headline) plus six palette cards, each a category title over a swatch-strip
//  image, and a rounded "Continue" CTA. The first card ("Basic") is selected and
//  paints the accent border.
//
//  All coordinates below are the board's own canvas space (393x852), taken from the
//  rendered HTML/CSS (the DDS rowDims and the deterministic browser render), not the
//  design_document layer tree (which carries overlapping Sketch export groups).
//

#import "PaletteSelectionViewController.h"
#import "PaletteSelectionStyle.h"
#import "PaletteCardView.h"

static NSString *const kAssetHeaderBackground = @"palette_header_background"; // 393x365
static NSString *const kAssetNavBack = @"palette_nav_back";                   // 32x32
static NSString *const kAssetStatusCellular = @"palette_status_cellular";     // 18x12
static NSString *const kAssetStatusWifi = @"palette_status_wifi";             // 16x12
static NSString *const kAssetStatusBattery = @"palette_status_battery";       // 25x12
static NSString *const kAssetCtaBackground = @"palette_cta_background";       // 393x190

static const CGFloat kCanvasWidth = 393.0;
static const CGFloat kCanvasHeight = 852.0;

static const CGFloat kCardCornerRadius = 12.0;
static const CGFloat kCardBorderWidth = 1.5;
static const CGFloat kProgressCornerRadius = 3.0;
static const CGFloat kCtaCornerRadius = 28.0;

/// One palette card: category title + swatch image + board-space frame + selection flag.
typedef struct {
    __unsafe_unretained NSString *title;
    __unsafe_unretained NSString *swatchImageName;
    CGFloat x;
    CGFloat y;
    CGFloat width;
    CGFloat height;
    BOOL selected;
} PaletteCardSpec;

/// Rendered order (top to bottom): Basic (selected), Make up, Pop, Macaron, Flowers,
/// Lively. Card frames are the board-space card rectangles.
static const PaletteCardSpec kPaletteCards[] = {
    {@"Basic",   @"palette_card_basic_swatches",   20.0, 206.0, 353.0, 102.0, YES},
    {@"Make up", @"palette_card_makeup_swatches",  20.0, 322.0, 353.0, 102.0, NO},
    {@"Pop",     @"palette_card_pop_swatches",     20.0, 438.0, 353.0, 102.0, NO},
    {@"Macaron", @"palette_card_macaron_swatches", 20.0, 554.0, 353.0, 102.0, NO},
    {@"Flowers", @"palette_card_flowers_swatches", 20.0, 670.0, 353.0, 102.0, NO},
    {@"Lively",  @"palette_card_lively_swatches",  20.0, 786.0, 353.0, 66.0,  NO},
};
static const NSUInteger kPaletteCardCount = sizeof(kPaletteCards) / sizeof(kPaletteCards[0]);

@interface PaletteSelectionViewController ()
@property(nonatomic, strong) UIView *canvasView;
@property(nonatomic, strong) UIImageView *headerBackgroundView;
@property(nonatomic, strong) UIImageView *statusCellularView;
@property(nonatomic, strong) UIImageView *statusWifiView;
@property(nonatomic, strong) UIImageView *statusBatteryView;
@property(nonatomic, strong) UILabel *statusTimeLabel;
@property(nonatomic, strong) UIImageView *navBackView;
@property(nonatomic, strong) UIView *progressTrackView;
@property(nonatomic, strong) UIView *progressFillView;
@property(nonatomic, strong) UILabel *skipLabel;
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UIImageView *ctaBackgroundView;
@property(nonatomic, strong) UIView *ctaButtonView;
@property(nonatomic, strong) UILabel *ctaLabel;
@property(nonatomic, strong) NSMutableArray<PaletteCardView *> *cardViews;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@end

@implementation PaletteSelectionViewController

#pragma mark - Design frames (board space)

- (CGRect)headerDesignFrame {
    return CGRectMake(0, 0, 393.0, 365.0);
}

- (CGRect)statusTimeDesignFrame {
    return CGRectMake(48.0, 14.0, 26.0, 20.0);
}

- (CGRect)statusCellularDesignFrame {
    return CGRectMake(294.0, 18.0, 17.0, 11.0);
}

- (CGRect)statusWifiDesignFrame {
    return CGRectMake(316.0, 17.0, 15.0, 11.0);
}

- (CGRect)statusBatteryDesignFrame {
    return CGRectMake(336.0, 17.0, 24.0, 11.0);
}

- (CGRect)navBackDesignFrame {
    return CGRectMake(12.0, 52.0, 32.0, 32.0);
}

- (CGRect)progressDesignFrame {
    return CGRectMake(81.0, 65.0, 232.0, 6.0);
}

- (CGRect)skipDesignFrame {
    return CGRectMake(346.0, 60.0, 27.0, 17.0);
}

- (CGRect)titleDesignFrame {
    return CGRectMake(41.0, 108.0, 311.0, 58.0);
}

- (CGRect)ctaDesignFrame {
    return CGRectMake(26.0, 728.0, 347.0, 56.0);
}

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];

    self.view.backgroundColor = PaletteSelectionStyle.pageBackgroundColor;
    self.view.accessibilityIdentifier = @"palette-selection";
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
          @"canvasDesignW=%.4f canvasDesignH=%.4f policy=fit",
          viewSize.width, viewSize.height, insets.top, insets.bottom,
          kCanvasWidth, kCanvasHeight);
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY page=palette-selection");
    [PaletteSelectionStyle logClosureCounters];
}

#pragma mark - Region assembly

- (void)buildRegions {
    self.hasBuiltRegions = YES;
    self.cardViews = [NSMutableArray array];

    // Canvas (393x852 board, fitted into the window).
    self.canvasView = [[UIView alloc] init];
    self.canvasView.backgroundColor = PaletteSelectionStyle.pageBackgroundColor;
    self.canvasView.clipsToBounds = YES;
    [self.view addSubview:self.canvasView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle fitCanvas:self.canvasView
                                                                  insideView:self.view]];

    CGSize canvasSize = CGSizeMake(kCanvasWidth, kCanvasHeight);

    [self buildHeaderInParent:self.canvasView canvasSize:canvasSize];
    [self buildCardsInParent:self.canvasView canvasSize:canvasSize];
    [self buildCtaInParent:self.canvasView canvasSize:canvasSize];
}

- (void)buildHeaderInParent:(UIView *)parent canvasSize:(CGSize)canvasSize {
    // Header background (bitmap, 393x365).
    self.headerBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetHeaderBackground]];
    self.headerBackgroundView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.headerBackgroundView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.headerBackgroundView
                                                                       parent:parent
                                                                  designFrame:[self headerDesignFrame]
                                                             parentDesignSize:canvasSize]];

    // Status bar time.
    self.statusTimeLabel = [[UILabel alloc] init];
    self.statusTimeLabel.text = @"9:41";
    self.statusTimeLabel.font = PaletteSelectionStyle.statusFont;
    self.statusTimeLabel.textColor = UIColor.blackColor;
    self.statusTimeLabel.textAlignment = NSTextAlignmentLeft;
    [parent addSubview:self.statusTimeLabel];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.statusTimeLabel
                                                                       parent:parent
                                                                  designFrame:[self statusTimeDesignFrame]
                                                             parentDesignSize:canvasSize
                                                                     sizeMode:PaletteClosureSizeIntrinsic
                                                                       anchor:PaletteClosureAnchorLeading]];

    // Status icons.
    self.statusCellularView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetStatusCellular]];
    self.statusCellularView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.statusCellularView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.statusCellularView
                                                                       parent:parent
                                                                  designFrame:[self statusCellularDesignFrame]
                                                             parentDesignSize:canvasSize]];

    self.statusWifiView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetStatusWifi]];
    self.statusWifiView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.statusWifiView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.statusWifiView
                                                                       parent:parent
                                                                  designFrame:[self statusWifiDesignFrame]
                                                             parentDesignSize:canvasSize]];

    self.statusBatteryView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetStatusBattery]];
    self.statusBatteryView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.statusBatteryView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.statusBatteryView
                                                                       parent:parent
                                                                  designFrame:[self statusBatteryDesignFrame]
                                                             parentDesignSize:canvasSize]];

    // Back button.
    self.navBackView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetNavBack]];
    self.navBackView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.navBackView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.navBackView
                                                                       parent:parent
                                                                  designFrame:[self navBackDesignFrame]
                                                             parentDesignSize:canvasSize]];

    // Progress track + fill.
    self.progressTrackView = [[UIView alloc] init];
    self.progressTrackView.backgroundColor = PaletteSelectionStyle.progressTrackColor;
    self.progressTrackView.layer.cornerRadius = kProgressCornerRadius;
    self.progressTrackView.layer.masksToBounds = YES;
    [parent addSubview:self.progressTrackView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.progressTrackView
                                                                       parent:parent
                                                                  designFrame:[self progressDesignFrame]
                                                             parentDesignSize:canvasSize]];

    self.progressFillView = [[UIView alloc] init];
    self.progressFillView.backgroundColor = PaletteSelectionStyle.progressFillColor;
    self.progressFillView.layer.cornerRadius = kProgressCornerRadius;
    self.progressFillView.layer.masksToBounds = YES;
    [self.progressTrackView addSubview:self.progressFillView];
    self.progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.progressFillView.leadingAnchor constraintEqualToAnchor:self.progressTrackView.leadingAnchor],
        [self.progressFillView.topAnchor constraintEqualToAnchor:self.progressTrackView.topAnchor],
        [self.progressFillView.bottomAnchor constraintEqualToAnchor:self.progressTrackView.bottomAnchor],
        [self.progressFillView.widthAnchor constraintEqualToConstant:24.0],
    ]];

    // Skip label.
    self.skipLabel = [[UILabel alloc] init];
    self.skipLabel.text = @"Skip";
    self.skipLabel.font = PaletteSelectionStyle.skipFont;
    self.skipLabel.textColor = PaletteSelectionStyle.skipTextColor;
    self.skipLabel.textAlignment = NSTextAlignmentLeft;
    [parent addSubview:self.skipLabel];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.skipLabel
                                                                       parent:parent
                                                                  designFrame:[self skipDesignFrame]
                                                             parentDesignSize:canvasSize
                                                                     sizeMode:PaletteClosureSizeIntrinsic
                                                                       anchor:PaletteClosureAnchorLeading]];

    // Headline (two lines, right aligned).
    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.text = @"Which palettes resonates with you the most?";
    self.titleLabel.font = PaletteSelectionStyle.headlineFont;
    self.titleLabel.textColor = PaletteSelectionStyle.primaryTextColor;
    self.titleLabel.textAlignment = NSTextAlignmentRight;
    self.titleLabel.numberOfLines = 0;
    [parent addSubview:self.titleLabel];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.titleLabel
                                                                       parent:parent
                                                                  designFrame:[self titleDesignFrame]
                                                             parentDesignSize:canvasSize]];
}

- (void)buildCardsInParent:(UIView *)parent canvasSize:(CGSize)canvasSize {
    for (NSUInteger i = 0; i < kPaletteCardCount; i++) {
        PaletteCardSpec spec = kPaletteCards[i];

        PaletteCardView *card = [[PaletteCardView alloc] init];
        card.title = spec.title;
        card.swatchImageName = spec.swatchImageName;
        card.selected = spec.selected;
        [parent addSubview:card];
        [self.cardViews addObject:card];

        CGRect designFrame = CGRectMake(spec.x, spec.y, spec.width, spec.height);
        [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:card
                                                                           parent:parent
                                                                      designFrame:designFrame
                                                                 parentDesignSize:canvasSize]];
    }
}

- (void)buildCtaInParent:(UIView *)parent canvasSize:(CGSize)canvasSize {
    // CTA background bitmap (393x190, anchored to the lower board region).
    self.ctaBackgroundView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:kAssetCtaBackground]];
    self.ctaBackgroundView.contentMode = UIViewContentModeScaleToFill;
    [parent addSubview:self.ctaBackgroundView];
    CGRect ctaBgFrame = CGRectMake(0, 662.0, 393.0, 190.0);
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.ctaBackgroundView
                                                                       parent:parent
                                                                  designFrame:ctaBgFrame
                                                             parentDesignSize:canvasSize]];

    // Continue button (rounded pill).
    self.ctaButtonView = [[UIView alloc] init];
    self.ctaButtonView.backgroundColor = PaletteSelectionStyle.ctaBackgroundColor;
    self.ctaButtonView.layer.cornerRadius = kCtaCornerRadius;
    self.ctaButtonView.layer.masksToBounds = YES;
    [parent addSubview:self.ctaButtonView];
    [NSLayoutConstraint activateConstraints:[PaletteSelectionStyle closeChild:self.ctaButtonView
                                                                       parent:parent
                                                                  designFrame:[self ctaDesignFrame]
                                                             parentDesignSize:canvasSize]];

    self.ctaLabel = [[UILabel alloc] init];
    self.ctaLabel.text = @"Continue";
    self.ctaLabel.font = PaletteSelectionStyle.ctaFont;
    self.ctaLabel.textColor = PaletteSelectionStyle.onCtaTextColor;
    self.ctaLabel.textAlignment = NSTextAlignmentCenter;
    [self.ctaButtonView addSubview:self.ctaLabel];
    self.ctaLabel.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [self.ctaLabel.centerXAnchor constraintEqualToAnchor:self.ctaButtonView.centerXAnchor],
        [self.ctaLabel.centerYAnchor constraintEqualToAnchor:self.ctaButtonView.centerYAnchor],
    ]];
}

@end
