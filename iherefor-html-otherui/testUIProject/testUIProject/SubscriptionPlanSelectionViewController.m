#import "SubscriptionPlanSelectionViewController.h"

static const CGFloat kCanvasWidth = 393.0;
static const CGFloat kCanvasHeight = 852.0;

@interface SubscriptionPlanSelectionViewController ()
@property(nonatomic) CGFloat sx;
@property(nonatomic) CGFloat sy;
@end

@implementation SubscriptionPlanSelectionViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithRed:241/255.0 green:240/255.0 blue:242/255.0 alpha:1];
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;
    self.view.accessibilityIdentifier = @"subscription-plan-selection";
    CGRect screenBounds = [UIScreen mainScreen].bounds;
    NSLog(@"IHEREFOR_RUNTIME_SCREEN_BOUNDS width=%.4f height=%.4f", screenBounds.size.width, screenBounds.size.height);
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    self.sx = self.view.bounds.size.width / kCanvasWidth;
    self.sy = self.view.bounds.size.height / kCanvasHeight;
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f scaleX=%.8f scaleY=%.8f", self.view.bounds.size.width, self.view.bounds.size.height, self.sx, self.sy);
    [self rebuildIfNeeded];
}

- (CGRect)map:(CGFloat)x y:(CGFloat)y w:(CGFloat)w h:(CGFloat)h {
    return CGRectMake(x * self.sx, y * self.sy, w * self.sx, h * self.sy);
}

- (UIFont *)font:(CGFloat)size weight:(UIFontWeight)weight {
    NSString *name = weight >= UIFontWeightBlack ? @"Avenir-Heavy" : (weight >= UIFontWeightSemibold ? @"Avenir-Medium" : @"Avenir-Medium");
    UIFont *font = [UIFont fontWithName:name size:size * MIN(self.sx, self.sy)];
    return font ?: [UIFont systemFontOfSize:size * MIN(self.sx, self.sy) weight:weight];
}

- (UIImage *)asset:(NSString *)name {
    NSString *path = [[NSBundle mainBundle] pathForResource:name ofType:@"png"];
    UIImage *image = path.length ? [UIImage imageWithContentsOfFile:path] : nil;
    if (!image) image = [UIImage imageNamed:name];
    NSLog(@"IHEREFOR_ASSET name=%@ loaded=%@ size=%@", name, image ? @"YES" : @"NO", image ? NSStringFromCGSize(image.size) : @"<nil>");
    return image;
}

- (UIImageView *)mappedImageView:(NSString *)name frame:(CGRect)frame contentMode:(UIViewContentMode)contentMode {
    UIImageView *view = [[UIImageView alloc] initWithFrame:frame];
    view.translatesAutoresizingMaskIntoConstraints = YES;
    view.image = [self asset:name];
    view.contentMode = contentMode;
    view.clipsToBounds = YES;
    view.layer.contents = (id)view.image.CGImage;
    view.layer.contentsScale = UIScreen.mainScreen.scale;
    view.layer.contentsGravity = (contentMode == UIViewContentModeScaleAspectFit) ? kCAGravityResizeAspect : kCAGravityResize;
    NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ x=%.3f y=%.3f w=%.3f h=%.3f naturalW=%.3f naturalH=%.3f scale=%.3f", name, frame.origin.x, frame.origin.y, frame.size.width, frame.size.height, view.image.size.width, view.image.size.height, UIScreen.mainScreen.scale);
    return view;
}

- (UILabel *)label:(NSString *)text frame:(CGRect)frame size:(CGFloat)size weight:(UIFontWeight)weight color:(UIColor *)color {
    UILabel *l = [[UILabel alloc] initWithFrame:frame];
    l.text = text; l.textColor = color; l.font = [self font:size weight:weight];
    l.numberOfLines = 0; l.adjustsFontSizeToFitWidth = NO;
    return l;
}

- (void)rebuildIfNeeded {
    if (self.view.subviews.count > 0) return;
    UIView *page = [[UIView alloc] initWithFrame:self.view.bounds];
    page.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.view addSubview:page];

    UIImageView *hero = [self mappedImageView:@"plan_selection_hero_collage" frame:[self map:0 y:0 w:393 h:321] contentMode:UIViewContentModeScaleToFill];
    [page addSubview:hero];

    UIButton *restoreTop = [UIButton buttonWithType:UIButtonTypeSystem]; restoreTop.frame = [self map:290 y:46 w:87 h:34];
    [restoreTop setTitle:@"Restore" forState:UIControlStateNormal]; restoreTop.titleLabel.font = [self font:14 weight:UIFontWeightMedium];
    [restoreTop setTitleColor:UIColor.whiteColor forState:UIControlStateNormal]; [restoreTop addTarget:self action:@selector(didTapRestore:) forControlEvents:UIControlEventTouchUpInside]; [page addSubview:restoreTop];

    UILabel *title = [self label:@"Choose Your Plan" frame:[self map:26 y:263 w:237 h:30] size:24 weight:UIFontWeightBlack color:[UIColor colorWithWhite:0.086 alpha:1]]; [page addSubview:title];
    UIImageView *crown = [self mappedImageView:@"plan_selection_title_crown.png" frame:[self map:231 y:261 w:32 h:32] contentMode:UIViewContentModeScaleToFill]; crown.alpha = 1.0; crown.layer.zPosition = 20; [page addSubview:crown];
    UIButton *close = [UIButton buttonWithType:UIButtonTypeCustom]; close.frame = [self map:16 y:52 w:32 h:32]; [close setImage:[self asset:@"plan_selection_close_icon"] forState:UIControlStateNormal]; [close addTarget:self action:@selector(didTapClose:) forControlEvents:UIControlEventTouchUpInside]; [page addSubview:close];

    UIImageView *portrait = [self mappedImageView:@"plan_selection_hero_portrait.png" frame:[self map:157 y:22 w:201 h:201] contentMode:UIViewContentModeScaleToFill]; portrait.alpha = 1.0; portrait.layer.zPosition = 20; portrait.layer.shadowColor=UIColor.blackColor.CGColor; portrait.layer.shadowOpacity=.16; portrait.layer.shadowRadius=3; [page addSubview:portrait];
    UIImageView *check = [self mappedImageView:@"plan_selection_trial_checkmark" frame:[self map:326 y:404 w:28 h:28] contentMode:UIViewContentModeScaleToFill]; [page addSubview:check];

    UILabel *desc = [self label:@"Unlock all Color Me features and enjoy an ad-free experience. Cancel anytime." frame:[self map:26 y:319 w:323 h:54] size:15 weight:UIFontWeightMedium color:[UIColor colorWithWhite:.086 alpha:1]]; desc.numberOfLines=2; [page addSubview:desc];
    [self addTrialCardTo:page];
    [page bringSubviewToFront:check];
    UILabel *expires=[self label:@"Expires today $0.00" frame:[self map:39 y:462 w:160 h:18] size:10 weight:UIFontWeightHeavy color:UIColor.blackColor]; [page addSubview:expires];
    UILabel *free=[self label:@"3 days free" frame:[self map:283 y:462 w:90 h:18] size:10 weight:UIFontWeightBlack color:[UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1]]; free.textAlignment=NSTextAlignmentRight; [page addSubview:free];
    [self addPlanCardsTo:page];
    UILabel *best=[self label:@"Best Value" frame:[self map:246 y:566 w:100 h:56] size:12 weight:UIFontWeightHeavy color:UIColor.whiteColor]; best.textAlignment=NSTextAlignmentCenter; best.backgroundColor=[UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1]; best.layer.cornerRadius=12; best.clipsToBounds=YES; [page addSubview:best];

    UIButton *cta = [UIButton buttonWithType:UIButtonTypeCustom]; cta.frame=[self map:23 y:720 w:347 h:68]; cta.layer.cornerRadius=34*self.sy; cta.clipsToBounds=YES; [cta setBackgroundImage:[self asset:@"plan_selection_cta_background"] forState:UIControlStateNormal]; [cta setTitle:@"Try For Free" forState:UIControlStateNormal]; cta.titleLabel.font=[self font:20 weight:UIFontWeightHeavy]; [cta setTitleColor:UIColor.whiteColor forState:UIControlStateNormal]; [cta addTarget:self action:@selector(didTapTryForFree:) forControlEvents:UIControlEventTouchUpInside]; [page addSubview:cta];
    UILabel *privacy=[self label:@"Privacy                 Terms                 Restore" frame:[self map:83 y:800 w:232 h:20] size:12 weight:UIFontWeightMedium color:[UIColor colorWithWhite:.596 alpha:1]]; [page addSubview:privacy];
}

- (void)addTrialCardTo:(UIView *)page { UIImageView *bg=[[UIImageView alloc] initWithFrame:[self map:23 y:388 w:347 h:70]]; bg.image=[self asset:@"plan_selection_trial_card"]; bg.contentMode=UIViewContentModeScaleToFill; [page addSubview:bg]; UILabel *a=[self label:@"Free trial enabled" frame:[self map:39 y:401 w:190 h:22] size:16 weight:UIFontWeightHeavy color:[UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1]]; [page addSubview:a]; UILabel *b=[self label:@"Cancel anytime" frame:[self map:39 y:425 w:150 h:18] size:12 weight:UIFontWeightHeavy color:[UIColor colorWithWhite:.08 alpha:1]]; [page addSubview:b]; }
- (void)addPlanCardsTo:(UIView *)page { UIImageView *w=[[UIImageView alloc] initWithFrame:[self map:23 y:486 w:347 h:70]]; w.image=[self asset:@"plan_selection_weekly_card"]; w.contentMode=UIViewContentModeScaleToFill; [page addSubview:w]; UILabel *wl=[self label:@"Weekly" frame:[self map:39 y:508 w:90 h:22] size:16 weight:UIFontWeightHeavy color:UIColor.blackColor]; [page addSubview:wl]; UILabel *wt=[self label:@"3 days free trial" frame:[self map:176 y:503 w:125 h:24] size:10 weight:UIFontWeightHeavy color:UIColor.blackColor]; wt.textAlignment=NSTextAlignmentCenter; wt.backgroundColor=[UIColor colorWithWhite:.9 alpha:1]; wt.layer.cornerRadius=15; wt.clipsToBounds=YES; [page addSubview:wt]; UILabel *wp=[self label:@"Then $7.99/week" frame:[self map:236 y:533 w:120 h:16] size:10 weight:UIFontWeightMedium color:UIColor.blackColor]; [page addSubview:wp]; UIImageView *y=[[UIImageView alloc] initWithFrame:[self map:23 y:580 w:347 h:70]]; y.image=[self asset:@"plan_selection_yearly_card"]; y.contentMode=UIViewContentModeScaleToFill; [page addSubview:y]; UILabel *yl=[self label:@"Yearly" frame:[self map:39 y:596 w:90 h:22] size:16 weight:UIFontWeightHeavy color:UIColor.blackColor]; [page addSubview:yl]; UILabel *ys=[self label:@"$49.99/year" frame:[self map:39 y:620 w:100 h:16] size:10 weight:UIFontWeightMedium color:UIColor.blackColor]; [page addSubview:ys]; UILabel *yp=[self label:@"Then $0.95/week" frame:[self map:239 y:618 w:120 h:16] size:10 weight:UIFontWeightMedium color:UIColor.blackColor]; [page addSubview:yp]; }

- (void)didTapTryForFree:(id)sender { /* TODO: connect business action */ }
- (void)didTapRestore:(id)sender { /* TODO: connect business action */ }
- (void)didTapClose:(id)sender { /* TODO: connect business action */ }
@end
