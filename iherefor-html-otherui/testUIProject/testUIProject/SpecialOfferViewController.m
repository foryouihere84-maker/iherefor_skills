//
//  SpecialOfferViewController.m
//  testUIProject
//
//  Special offer paywall (Lanhu image_id 7b573b85-1167-4a04-a9e1-a4575566f5a4).
//
//  Layout contract: every frame below is written in Lanhu canvas coordinates
//  (393 x 852, index.css `.page`) and converted through SpecialOfferStyle, which
//  owns the single scaleX/scaleY pair measured from the runtime device API.
//  Image frames, font sizes, corner radii and line heights all pass through the
//  same mapper - no region is allowed to hand-tune its own ratio.
//
//  The HTML paints the hero artwork as a full-bleed layer with no safe-area inset
//  anywhere in the document, so the page deliberately does not honour the safe
//  area: system bars overlay the artwork exactly as they do in the browser
//  baseline. See ui-implementation-plan.json -> systemBars.
//

#import "SpecialOfferViewController.h"
#import "SpecialOfferPlanCardView.h"
#import "SpecialOfferPrimaryButton.h"
#import "SpecialOfferStyle.h"

#pragma mark - Asset names

static NSString *const kAssetCloseIcon = @"special_offer_close_icon";
static NSString *const kAssetHeroBackground = @"special_offer_hero_background";
static NSString *const kAssetHeroBadge = @"special_offer_hero_special_offer_badge";
static NSString *const kAssetWeeklyCard = @"special_offer_weekly_card_background";
static NSString *const kAssetYearlyCard = @"special_offer_yearly_card_background";

/// The 60pt headline is the only black-weight text that does not share its CSS
/// size with another element, so it is identified by its literal text.
static NSString *const kSpecialOfferHeadlineText = @"50% OFF";

@interface SpecialOfferViewController ()
@property(nonatomic, strong) SpecialOfferStyle *style;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@property(nonatomic, assign) CGSize builtDeviceSize;
@property(nonatomic, strong) UIView *pageView;
@end

@implementation SpecialOfferViewController

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = SpecialOfferStyle.pageBackgroundColor;
    self.view.accessibilityIdentifier = @"special-offer";
    // The Lanhu page starts at canvas y=0 with no system-bar inset: background
    // and content both underlap the status bar (systemBars.policy = underlap).
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;

    CGRect screenBounds = UIScreen.mainScreen.bounds;
    self.style = [SpecialOfferStyle styleForDeviceSize:screenBounds.size];
    NSLog(@"IHEREFOR_RUNTIME_SCREEN_BOUNDS width=%.4f height=%.4f scale=%.4f nativeScale=%.4f",
          screenBounds.size.width, screenBounds.size.height,
          UIScreen.mainScreen.scale, UIScreen.mainScreen.nativeScale);
    // Font substitution evidence: index.css names AvenirLT-Black, which is
    // installed in neither Chromium nor iOS. Log the measured candidates against
    // the reference advance width recorded in ui-implementation-plan.json.
    [SpecialOfferStyle logFontCandidatesForText:kSpecialOfferHeadlineText pointSize:60.0 referenceWidth:235.06];
}

- (UIStatusBarStyle)preferredStatusBarStyle {
    // Light hero artwork: the status bar glyphs must stay dark, matching the
    // light background rendered by Chromium in the HTML baseline.
    return UIStatusBarStyleDarkContent;
}

- (BOOL)prefersHomeIndicatorAutoHidden {
    return NO;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    // Re-anchor the mapper on the view's real bounds so the frames are derived
    // from the same API value that is written into runtime-device.json.
    self.style = [SpecialOfferStyle styleForDeviceSize:self.view.bounds.size];
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f safeTop=%.4f safeBottom=%.4f scaleX=%.8f scaleY=%.8f",
          self.view.bounds.size.width, self.view.bounds.size.height,
          self.view.safeAreaInsets.top, self.view.safeAreaInsets.bottom,
          self.style.canvasScale.x, self.style.canvasScale.y);
    if (!self.hasBuiltRegions || !CGSizeEqualToSize(self.builtDeviceSize, self.view.bounds.size)) {
        // The first layout pass can run before the window has its final bounds in
        // an iOS 26 scene; rebuilding on a bounds change keeps every mapped frame
        // anchored to the same device size that runtime-device.json records.
        [self.pageView removeFromSuperview];
        self.pageView = nil;
        self.hasBuiltRegions = YES;
        self.builtDeviceSize = self.view.bounds.size;
        [self buildRegions];
    }
    [self logImageFrames];
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY");
    // Emitted after the window transaction settles: links each named region to
    // its realised window-space frame so the screenshot can be audited against
    // the mapper prediction from outside the process.
    [self logRegionFramesInView:self.view
                       rootView:self.view];
}

- (void)logRegionFramesInView:(UIView *)view rootView:(UIView *)rootView {
    for (UIView *subview in view.subviews) {
        if (subview.accessibilityIdentifier.length && ![subview.accessibilityIdentifier isEqualToString:@"special-offer"]) {
            CGRect frameInRoot = [subview convertRect:subview.bounds toView:rootView];
            NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ class=%@ frameInRoot=%.3f,%.3f,%.3f,%.3f canvasOrigin=%.2f,%.2f canvasSize=%.2f,%.2f",
                  subview.accessibilityIdentifier, NSStringFromClass(subview.class),
                  frameInRoot.origin.x, frameInRoot.origin.y, frameInRoot.size.width, frameInRoot.size.height,
                  frameInRoot.origin.x / MAX(self.style.canvasScale.x, 0.0001),
                  frameInRoot.origin.y / MAX(self.style.canvasScale.y, 0.0001),
                  frameInRoot.size.width / MAX(self.style.canvasScale.x, 0.0001),
                  frameInRoot.size.height / MAX(self.style.canvasScale.y, 0.0001));
        }
        [self logRegionFramesInView:subview rootView:rootView];
    }
}

#pragma mark - Region construction

- (void)buildRegions {
    UIView *page = [[UIView alloc] initWithFrame:[self.style mappedRect:CGRectMake(0, 0, kSpecialOfferCanvasWidth, kSpecialOfferCanvasHeight)]];
    page.backgroundColor = SpecialOfferStyle.pageBackgroundColor;
    page.clipsToBounds = YES;
    page.accessibilityIdentifier = @"special-offer-page";
    page.translatesAutoresizingMaskIntoConstraints = YES;
    self.pageView = page;
    [self.view addSubview:page];

    [self buildHeroRegionInPage:page];
    [self buildOffersRegionInPage:page];

    NSLog(@"IHEREFOR_REGION_FRAME name=page x=%.3f y=%.3f w=%.3f h=%.3f",
          page.frame.origin.x, page.frame.origin.y, page.frame.size.width, page.frame.size.height);
}

#pragma mark - Region 1: hero

- (void)buildHeroRegionInPage:(UIView *)page {
    UIView *hero = [[UIView alloc] initWithFrame:[self.style mappedRect:CGRectMake(0, 0, kSpecialOfferCanvasWidth, 472)]];
    hero.clipsToBounds = YES;
    hero.accessibilityIdentifier = @"special-offer-hero";
    hero.translatesAutoresizingMaskIntoConstraints = YES;
    [page addSubview:hero];

    // .group_1 { background: url(img_1) 100% no-repeat; background-size: 100% 100%; }
    UIImageView *heroBackground = [self imageViewWithAsset:kAssetHeroBackground
                                                     frame:[self.style mappedRect:CGRectMake(0, 0, kSpecialOfferCanvasWidth, 472)]
                                               contentMode:UIViewContentModeScaleToFill];
    heroBackground.accessibilityIdentifier = @"special-offer-hero-background";
    [hero addSubview:heroBackground];

    // .label_1 { width:32px; height:32px; } at the group_1 padding origin (10, 52).
    UIButton *closeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    closeButton.frame = [self.style mappedRect:CGRectMake(10, 52, 32, 32)];
    closeButton.accessibilityIdentifier = @"special-offer-close";
    closeButton.accessibilityLabel = @"Close";
    closeButton.translatesAutoresizingMaskIntoConstraints = YES;
    UIImage *closeIcon = [self imageNamed:kAssetCloseIcon];
    [closeButton setImage:closeIcon forState:UIControlStateNormal];
    closeButton.imageView.contentMode = UIViewContentModeScaleAspectFit;
    [closeButton addTarget:self action:@selector(didTapClose:) forControlEvents:UIControlEventTouchUpInside];
    [hero addSubview:closeButton];
    NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ x=%.3f y=%.3f w=%.3f h=%.3f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleAspectFit",
          kAssetCloseIcon, closeButton.frame.origin.x, closeButton.frame.origin.y,
          closeButton.frame.size.width, closeButton.frame.size.height,
          closeIcon.size.width, closeIcon.size.height);

    // .paragraph_1 "50% OFF": 60px/58px, orange, right aligned inside the 266pt
    // (64 -> 330) line box produced by text-group_8 and its 54/19 margins.
    UILabel *headline = [self labelWithText:kSpecialOfferHeadlineText
                                canvasFrame:CGRectMake(64, 280, 266, 58)
                                  pointSize:60
                           canvasLineHeight:58
                                     weight:UIFontWeightBlack
                                      color:SpecialOfferStyle.headlineOrangeColor
                                  alignment:NSTextAlignmentRight
                                  styleName:@"headline"];
    headline.accessibilityIdentifier = @"special-offer-headline";
    [hero addSubview:headline];

    // .text_2 "Don't Miss Out" (24px/29px at x=105) and .text_3 "！" (24px at
    // x=255.27). The two spans carry different CSS families but both resolve to
    // the same rendered face in the browser baseline, so they share one font.
    UILabel *subtitle = [self labelWithText:@"Don’t Miss Out"
                                canvasFrame:CGRectMake(105, 348, 151, 29)
                                  pointSize:24
                           canvasLineHeight:29
                                     weight:UIFontWeightBlack
                                      color:SpecialOfferStyle.headlineAccentBlueColor
                                  alignment:NSTextAlignmentLeft
                                  styleName:@"subtitle"];
    subtitle.accessibilityIdentifier = @"special-offer-subtitle";
    [hero addSubview:subtitle];

    UILabel *bang = [self labelWithText:@"！"
                            canvasFrame:CGRectMake(256, 348, 24, 29)
                              pointSize:24
                       canvasLineHeight:29
                                 weight:UIFontWeightBlack
                                  color:SpecialOfferStyle.headlineAccentBlueColor
                              alignment:NSTextAlignmentLeft
                              styleName:@"subtitleMark"];
    bang.accessibilityIdentifier = @"special-offer-subtitle-mark";
    [hero addSubview:bang];

    // .text_15 feature description: 15px/18px, two lines, left aligned at x=26.
    UILabel *description = [self labelWithText:@"Unlock all Color Me features and enjoy an ad-free experience."
                                   canvasFrame:CGRectMake(26, 418, 323, 40)
                                     pointSize:15
                              canvasLineHeight:18
                                        weight:UIFontWeightMedium
                                         color:SpecialOfferStyle.bodyTextColor
                                     alignment:NSTextAlignmentLeft
                                     styleName:@"description"];
    description.numberOfLines = 2;
    description.accessibilityIdentifier = @"special-offer-description";
    [hero addSubview:description];

    // .image_1: absolutely positioned badge artwork, top -32, size 306x273, with
    // the asset painted at (0, 32) inside it at its declared 307x241 box.
    UIImageView *badgeImage = [self imageViewWithAsset:kAssetHeroBadge
                                                 frame:[self.style mappedRect:CGRectMake(43, -32, 306, 273)]
                                           contentMode:UIViewContentModeScaleToFill];
    badgeImage.accessibilityIdentifier = @"special-offer-hero-badge-artwork";
    [hero addSubview:badgeImage];

    // .text_1 "Your Special Offer": 24px/29px violet, x=92 on the page canvas.
    UILabel *badgeTitle = [self labelWithText:@"Your Special Offer"
                                  canvasFrame:CGRectMake(92, 241, 210, 29)
                                    pointSize:24
                             canvasLineHeight:29
                                       weight:UIFontWeightBlack
                                        color:SpecialOfferStyle.headlineAccentBlueColor
                                    alignment:NSTextAlignmentLeft
                                    styleName:@"badgeTitle"];
    badgeTitle.accessibilityIdentifier = @"special-offer-badge-title";
    [hero addSubview:badgeTitle];
}

#pragma mark - Region 2: offers block

// The offers block is a canvas-space subview placed at page canvas (0, 472); its
// children are therefore expressed in block-local coordinates, i.e. the page
// canvas value minus the block origin. Keeping this offset named is what stops
// the block offset from being applied twice.
static const CGFloat kOffersBlockCanvasOriginY = 472.0;

static CGRect SpecialOfferOffersLocalRect(CGFloat pageCanvasX, CGFloat pageCanvasY, CGFloat width, CGFloat height) {
    return CGRectMake(pageCanvasX, pageCanvasY - kOffersBlockCanvasOriginY, width, height);
}

- (void)buildOffersRegionInPage:(UIView *)page {
    UIView *offers = [[UIView alloc] initWithFrame:[self.style mappedRect:CGRectMake(0, kOffersBlockCanvasOriginY, kSpecialOfferCanvasWidth, 381)]];
    offers.clipsToBounds = NO;
    offers.accessibilityIdentifier = @"special-offer-plans";
    offers.translatesAutoresizingMaskIntoConstraints = YES;
    [page addSubview:offers];

    // .section_1 Weekly: page canvas 23,495 347x68 with 16/20 padding; the row is
    // space-between, so the title starts at x=39 and the price column is right
    // aligned to x=350.
    SpecialOfferPlanCardView *weekly = [[SpecialOfferPlanCardView alloc] initWithStyle:self.style
                                                                          canvasFrame:SpecialOfferOffersLocalRect(23, 495, 347, 68)
                                                                     backgroundImage:kAssetWeeklyCard
                                                                                 title:@"Weekly"
                                                                                 price:@"$3.99 /week"
                                                                                  note:nil];
    weekly.struckPriceText = @"$7.99 /week";
    weekly.accessibilityIdentifier = @"special-offer-weekly-card";
    [weekly addTarget:self action:@selector(didTapWeeklyPlan:) forControlEvents:UIControlEventTouchUpInside];
    [offers addSubview:weekly];

    // .section_2 Yearly: page canvas 23,590 347x68, note shown right aligned.
    SpecialOfferPlanCardView *yearly = [[SpecialOfferPlanCardView alloc] initWithStyle:self.style
                                                                          canvasFrame:SpecialOfferOffersLocalRect(23, 590, 347, 68)
                                                                     backgroundImage:kAssetYearlyCard
                                                                                 title:@"Yearly"
                                                                                 price:@"$49.99/year"
                                                                                  note:@"only $0.95/week"];
    yearly.accessibilityIdentifier = @"special-offer-yearly-card";
    [yearly addTarget:self action:@selector(didTapYearlyPlan:) forControlEvents:UIControlEventTouchUpInside];
    [offers addSubview:yearly];

    // .text-wrapper_3 pill CTA: page canvas 23,722 347x68, radius 34.
    SpecialOfferPrimaryButton *claimButton = [[SpecialOfferPrimaryButton alloc] initWithStyle:self.style
                                                                                 canvasFrame:SpecialOfferOffersLocalRect(23, 722, 347, 68)];
    [claimButton addTarget:self action:@selector(didTapClaimOffer:) forControlEvents:UIControlEventTouchUpInside];
    [offers addSubview:claimButton];

    // .text-wrapper_10 footer row: Privacy / Terms / Restore, 12px/16px grey.
    // Rendered as real buttons so each affordance is tappable and testable.
    [offers addSubview:[self footerButtonWithTitle:@"Privacy"
                                       canvasFrame:SpecialOfferOffersLocalRect(83, 802, 39, 16)
                                         alignment:NSTextAlignmentLeft
                                            action:@selector(didTapPrivacy:)
                                    accessibilityId:@"special-offer-footer-privacy"
                                          styleName:@"footerPrivacy"]];

    [offers addSubview:[self footerButtonWithTitle:@"Terms"
                                       canvasFrame:SpecialOfferOffersLocalRect(181, 802, 33, 16)
                                         alignment:NSTextAlignmentCenter
                                            action:@selector(didTapTerms:)
                                    accessibilityId:@"special-offer-footer-terms"
                                          styleName:@"footerTerms"]];

    [offers addSubview:[self footerButtonWithTitle:@"Restore"
                                       canvasFrame:SpecialOfferOffersLocalRect(273, 802, 42, 16)
                                         alignment:NSTextAlignmentCenter
                                            action:@selector(didTapRestore:)
                                    accessibilityId:@"special-offer-footer-restore"
                                          styleName:@"footerRestore"]];

    // .text-wrapper_5 "Best Value": 100x28, radius 6, violet, centred 10px/14px.
    UILabel *bestValue = [self labelWithText:@"Best Value"
                                 canvasFrame:SpecialOfferOffersLocalRect(246, 578, 100, 28)
                                   pointSize:10
                            canvasLineHeight:14
                                      weight:UIFontWeightBlack
                                       color:SpecialOfferStyle.onAccentTextColor
                                   alignment:NSTextAlignmentCenter
                                   styleName:@"badgeBestValue"];
    bestValue.backgroundColor = SpecialOfferStyle.badgeVioletColor;
    bestValue.layer.cornerRadius = [self.style mappedLength:6];
    bestValue.clipsToBounds = YES;
    bestValue.accessibilityIdentifier = @"special-offer-best-value-badge";
    [offers addSubview:bestValue];

    // .text-wrapper_8 "SAVE 50%": 100x28, radius 6, orange, centred 14px/19px.
    UILabel *saveBadge = [self labelWithText:@"SAVE 50%"
                                 canvasFrame:SpecialOfferOffersLocalRect(246, 481, 100, 28)
                                   pointSize:14
                            canvasLineHeight:19
                                      weight:UIFontWeightBlack
                                       color:SpecialOfferStyle.onAccentTextColor
                                   alignment:NSTextAlignmentCenter
                                   styleName:@"badgeSave"];
    saveBadge.backgroundColor = SpecialOfferStyle.badgeOrangeColor;
    saveBadge.layer.cornerRadius = [self.style mappedLength:6];
    saveBadge.clipsToBounds = YES;
    saveBadge.accessibilityIdentifier = @"special-offer-save-badge";
    [offers addSubview:saveBadge];
}

#pragma mark - Helpers

- (UILabel *)labelWithText:(NSString *)text
               canvasFrame:(CGRect)canvasFrame
                 pointSize:(CGFloat)pointSize
          canvasLineHeight:(CGFloat)canvasLineHeight
                    weight:(UIFontWeight)weight
                     color:(UIColor *)color
                 alignment:(NSTextAlignment)alignment
                 styleName:(NSString *)styleName {
    UILabel *label = [[UILabel alloc] initWithFrame:[self.style mappedRect:canvasFrame]];
    label.text = text;
    // index.css names AvenirLT-*/Avenir-*/PingFangSC-* faces that are installed in
    // neither Chromium (the reference) nor iOS, so the substitute is measured
    // against the reference advance width for this exact element, not assumed.
    label.font = [SpecialOfferStyle fontForText:text
                                          class:(weight >= UIFontWeightBlack ? SpecialOfferFontWeightClassBlack : SpecialOfferFontWeightClassMedium)
                                      pointSize:[self.style mappedLength:pointSize]
                                 referenceWidth:[SpecialOfferStyle referenceWidthForStyle:styleName] * self.style.canvasScale.x];
    label.textColor = color;
    label.textAlignment = alignment;
    label.numberOfLines = 1;
    label.translatesAutoresizingMaskIntoConstraints = YES;
    label.lineBreakMode = NSLineBreakByClipping;
    return label;
}

- (UIButton *)footerButtonWithTitle:(NSString *)title
                        canvasFrame:(CGRect)canvasFrame
                          alignment:(NSTextAlignment)alignment
                             action:(SEL)action
                   accessibilityId:(NSString *)accessibilityId
                          styleName:(NSString *)styleName {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeCustom];
    button.frame = [self.style mappedRect:canvasFrame];
    button.translatesAutoresizingMaskIntoConstraints = YES;
    button.accessibilityIdentifier = accessibilityId;
    button.contentHorizontalAlignment = (alignment == NSTextAlignmentLeft)
        ? UIControlContentHorizontalAlignmentLeft
        : UIControlContentHorizontalAlignmentCenter;
    button.titleLabel.font = [SpecialOfferStyle fontForText:title
                                                      class:SpecialOfferFontWeightClassMedium
                                                  pointSize:[self.style mappedLength:12]
                                             referenceWidth:[SpecialOfferStyle referenceWidthForStyle:styleName] * self.style.canvasScale.x];
    [button setTitle:title forState:UIControlStateNormal];
    [button setTitleColor:SpecialOfferStyle.footerLinkColor forState:UIControlStateNormal];
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    return button;
}

- (UIImage *)imageNamed:(NSString *)name {
    UIImage *image = [UIImage imageNamed:name];
    if (!image) {
        NSString *path = [[NSBundle mainBundle] pathForResource:name ofType:@"png"];
        if (path.length) {
            image = [UIImage imageWithContentsOfFile:path];
        }
    }
    return image;
}

- (UIImageView *)imageViewWithAsset:(NSString *)name
                              frame:(CGRect)frame
                        contentMode:(UIViewContentMode)contentMode {
    UIImage *image = [self imageNamed:name];
    UIImageView *view = [[UIImageView alloc] initWithFrame:frame];
    view.image = image;
    view.contentMode = contentMode;
    // The HTML paints this artwork with background-size 100% 100%, so the drawn
    // content must stretch to the mapped frame instead of falling back to the
    // asset's intrinsic pixel size.
    view.clipsToBounds = YES;
    view.translatesAutoresizingMaskIntoConstraints = YES;
    view.layer.contents = (id)image.CGImage;
    view.layer.contentsScale = UIScreen.mainScreen.scale;
    view.layer.contentsGravity = (contentMode == UIViewContentModeScaleAspectFit) ? kCAGravityResizeAspect : kCAGravityResize;
    view.accessibilityIdentifier = name;
    NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ x=%.3f y=%.3f w=%.3f h=%.3f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
          name, frame.origin.x, frame.origin.y, frame.size.width, frame.size.height,
          image.size.width, image.size.height);
    return view;
}

/// Re-reads the realised frames from the live layer tree so the screenshot can
/// be checked against the mapper prediction instead of the construction values.
- (void)logImageFrames {
    [self logImageFramesInView:self.view];
}

- (void)logImageFramesInView:(UIView *)view {
    for (UIView *subview in view.subviews) {
        if ([subview isKindOfClass:UIImageView.class]) {
            UIImageView *imageView = (UIImageView *)subview;
            CGRect frameInWindow = [subview convertRect:subview.bounds toView:nil];
            NSLog(@"IHEREFOR_LAYER_IMAGE name=%@ frameInWindow=%.3f,%.3f,%.3f,%.3f bounds=%.3f,%.3f,%.3f,%.3f contentsGravity=%@ alpha=%.2f",
                  subview.accessibilityIdentifier ?: @"<unnamed>",
                  frameInWindow.origin.x, frameInWindow.origin.y, frameInWindow.size.width, frameInWindow.size.height,
                  imageView.bounds.origin.x, imageView.bounds.origin.y, imageView.bounds.size.width, imageView.bounds.size.height,
                  imageView.layer.contentsGravity, imageView.alpha);
        }
        [self logImageFramesInView:subview];
    }
}

#pragma mark - Actions (TODO: connect business action)

- (void)didTapClose:(id)sender {
    // TODO: connect business action - dismiss the paywall.
}

- (void)didTapWeeklyPlan:(id)sender {
    // TODO: connect business action - select the weekly plan.
}

- (void)didTapYearlyPlan:(id)sender {
    // TODO: connect business action - select the yearly plan.
}

- (void)didTapClaimOffer:(id)sender {
    // TODO: connect business action - start the purchase flow.
}

- (void)didTapPrivacy:(id)sender {
    // TODO: connect business action - open the privacy policy.
}

- (void)didTapTerms:(id)sender {
    // TODO: connect business action - open the terms of use.
}

- (void)didTapRestore:(id)sender {
    // TODO: connect business action - restore purchases.
}

@end
