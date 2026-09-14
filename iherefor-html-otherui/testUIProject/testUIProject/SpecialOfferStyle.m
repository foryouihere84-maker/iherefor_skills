//
//  SpecialOfferStyle.m
//  testUIProject
//

#import "SpecialOfferStyle.h"

const CGFloat kSpecialOfferCanvasWidth = 393.0;
const CGFloat kSpecialOfferCanvasHeight = 852.0;

@implementation SpecialOfferStyle

+ (instancetype)styleForDeviceSize:(CGSize)deviceSize {
    return [[self alloc] initWithDeviceSize:deviceSize];
}

- (instancetype)initWithDeviceSize:(CGSize)deviceSize {
    self = [super init];
    if (self) {
        _deviceSize = deviceSize;
        _canvasScale = CGPointMake(deviceSize.width / kSpecialOfferCanvasWidth,
                                   deviceSize.height / kSpecialOfferCanvasHeight);
    }
    return self;
}

- (CGRect)mappedRect:(CGRect)canvasRect {
    return CGRectMake(canvasRect.origin.x * self.canvasScale.x,
                      canvasRect.origin.y * self.canvasScale.y,
                      canvasRect.size.width * self.canvasScale.x,
                      canvasRect.size.height * self.canvasScale.y);
}

- (CGFloat)mappedLength:(CGFloat)canvasLength {
    return canvasLength * MIN(self.canvasScale.x, self.canvasScale.y);
}

+ (UIColor *)pageBackgroundColor {
    return [UIColor colorWithRed:241 / 255.0 green:240 / 255.0 blue:242 / 255.0 alpha:1];
}

+ (UIColor *)headlineOrangeColor {
    return [UIColor colorWithRed:254 / 255.0 green:123 / 255.0 blue:27 / 255.0 alpha:1];
}

+ (UIColor *)headlineAccentBlueColor {
    return [UIColor colorWithRed:89 / 255.0 green:87 / 255.0 blue:255 / 255.0 alpha:1];
}

+ (UIColor *)bodyTextColor {
    return [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 blue:22 / 255.0 alpha:1];
}

+ (UIColor *)planTitleColor {
    return [UIColor colorWithRed:20 / 255.0 green:20 / 255.0 blue:20 / 255.0 alpha:1];
}

+ (UIColor *)planDetailColor {
    return [UIColor colorWithRed:20 / 255.0 green:20 / 255.0 blue:20 / 255.0 alpha:1];
}

+ (UIColor *)footerLinkColor {
    return [UIColor colorWithRed:152 / 255.0 green:151 / 255.0 blue:149 / 255.0 alpha:1];
}

+ (UIColor *)badgeVioletColor {
    return [self headlineAccentBlueColor];
}

+ (UIColor *)badgeOrangeColor {
    return [self headlineOrangeColor];
}

+ (UIColor *)onAccentTextColor {
    return UIColor.whiteColor;
}

#pragma mark - Typography

// Reference advance widths and CSS font sizes, measured from the HTML baseline
// (browser DOM range measurements at the 402x874 viewport; see
// ui-implementation-plan.json -> typography.referenceAdvances).
static NSDictionary<NSString *, NSArray<NSNumber *> *> *SpecialOfferTextMetrics(void) {
    static NSDictionary *metrics = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        // style name       CSS pointSize  reference advance width
        metrics = @{
            @"headline":        @[@60.0, @235.06],
            @"subtitle":        @[@24.0, @150.27],
            @"subtitleMark":    @[@24.0, @24.00],
            @"description":     @[@15.0, @279.08],
            @"badgeTitle":      @[@24.0, @181.13],
            @"planTitleWeekly": @[@16.0, @54.84],
            @"planTitleYearly": @[@16.0, @45.08],
            @"planPriceCurrent":@[@10.0, @55.00],
            @"planPriceStruck": @[@10.0, @55.00],
            @"planYearlyPrice": @[@10.0, @53.92],
            @"planNote":        @[@10.0, @74.50],
            @"ctaTitle":        @[@20.0, @142.63],
            @"footerPrivacy":   @[@12.0, @38.45],
            @"footerTerms":     @[@12.0, @32.23],
            @"footerRestore":   @[@12.0, @41.80],
            @"badgeBestValue":  @[@10.0, @49.09],
            @"badgeSave":       @[@14.0, @68.59],
            @"badgeSaveUnit":   @[@10.0, @0.00],
        };
    });
    return metrics;
}

+ (CGFloat)referenceWidthForStyle:(NSString *)styleName {
    NSArray<NSNumber *> *entry = SpecialOfferTextMetrics()[styleName];
    return entry ? entry[1].doubleValue : 0.0;
}

+ (CGFloat)pointSizeForStyle:(NSString *)styleName {
    NSArray<NSNumber *> *entry = SpecialOfferTextMetrics()[styleName];
    return entry ? entry[0].doubleValue : 0.0;
}

/// Faces that may stand in for the AvenirLT/Avenir family declared by index.css.
static NSArray<NSString *> *SpecialOfferFontCandidates(void) {
    return @[
        @"Avenir-Black", @"Avenir-Heavy", @"Avenir-Medium", @"Avenir-Book",
        @"AvenirNext-Bold", @"AvenirNext-DemiBold", @"AvenirNext-Medium", @"AvenirNext-Regular",
        @"HelveticaNeue-Bold", @"HelveticaNeue-Medium", @"HelveticaNeue",
        @"Arial-BoldMT", @"ArialMT",
        @"PingFangSC-Semibold", @"PingFangSC-Medium", @"PingFangTC-Medium",
        @"HiraginoSans-W8", @"HiraginoSans-W6", @"HiraginoSans-W3",
    ];
}

+ (UIFont *)fontForText:(NSString *)text
                  class:(SpecialOfferFontWeightClass)weightClass
              pointSize:(CGFloat)pointSize
         referenceWidth:(CGFloat)referenceWidth {
    if (pointSize <= 0) {
        return [UIFont systemFontOfSize:1];
    }
    NSArray<NSString *> *preferred = (weightClass == SpecialOfferFontWeightClassBlack)
        ? @[@"Avenir-Black", @"Avenir-Heavy", @"AvenirNext-Bold", @"HelveticaNeue-Bold", @"Arial-BoldMT"]
        : @[@"Avenir-Medium", @"AvenirNext-Medium", @"HelveticaNeue-Medium", @"PingFangSC-Medium", @"ArialMT"];
    NSArray<NSString *> *candidates = [preferred arrayByAddingObjectsFromArray:SpecialOfferFontCandidates()];

    UIFont *bestFont = nil;
    CGFloat bestDelta = CGFLOAT_MAX;
    CGFloat bestWidth = 0;
    NSMutableSet<NSString *> *seen = [NSMutableSet set];
    for (NSString *face in candidates) {
        if ([seen containsObject:face]) continue;
        [seen addObject:face];
        UIFont *font = [UIFont fontWithName:face size:pointSize];
        if (!font) continue;
        CGFloat width = [text sizeWithAttributes:@{NSFontAttributeName : font}].width;
        if (width <= 0) continue;
        CGFloat delta = referenceWidth > 0 ? fabs(width - referenceWidth) : 0;
        if (delta < bestDelta) {
            bestDelta = delta;
            bestFont = font;
            bestWidth = width;
        }
        if (referenceWidth <= 0) break;
    }
    if (!bestFont) {
        bestFont = [UIFont systemFontOfSize:pointSize weight:UIFontWeightBold];
        bestWidth = [text sizeWithAttributes:@{NSFontAttributeName : bestFont}].width;
    }

    // Keep the CSS line box but clamp the glyph size so the realised advance
    // width matches the reference render. The 0.80-1.20 bounds stop a bad
    // candidate from silently changing the type hierarchy.
    UIFont *resolved = bestFont;
    CGFloat scale = 1.0;
    if (referenceWidth > 0 && bestWidth > 0) {
        scale = MAX(0.80, MIN(1.20, referenceWidth / bestWidth));
        if (fabs(scale - 1.0) > 0.005) {
            UIFont *scaled = [UIFont fontWithName:bestFont.fontName size:pointSize * scale];
            if (scaled) {
                resolved = scaled;
            } else {
                scale = 1.0;
            }
        } else {
            scale = 1.0;
        }
    }
    NSLog(@"IHEREFOR_FONT_RESOLVED text=%@ cssPointSize=%.2f class=%@ referenceWidth=%.2f chosenFace=%@ chosenWidth=%.2f glyphScale=%.4f finalPointSize=%.2f",
          text, pointSize, weightClass == SpecialOfferFontWeightClassBlack ? @"black" : @"medium",
          referenceWidth, bestFont.fontName, bestWidth, scale, resolved.pointSize);
    return resolved;
}

+ (void)logFontCandidatesForText:(NSString *)text
                       pointSize:(CGFloat)pointSize
                  referenceWidth:(CGFloat)referenceWidth {
    NSMutableArray<NSString *> *lines = [NSMutableArray array];
    for (NSString *face in SpecialOfferFontCandidates()) {
        UIFont *font = [UIFont fontWithName:face size:pointSize];
        if (!font) continue;
        CGFloat width = [text sizeWithAttributes:@{NSFontAttributeName : font}].width;
        [lines addObject:[NSString stringWithFormat:@"%@=%.2f(d=%.2f)", face, width, fabs(width - referenceWidth)]];
    }
    NSLog(@"IHEREFOR_FONT_CANDIDATES text=%@ pointSize=%.2f referenceWidth=%.2f %@",
          text, pointSize, referenceWidth, [lines componentsJoinedByString:@" "]);
}

+ (UIFont *)avenirFontOfSize:(CGFloat)pointSize weight:(UIFontWeight)weight {
    return [self fontForText:@"M"
                       class:(weight >= UIFontWeightBold ? SpecialOfferFontWeightClassBlack : SpecialOfferFontWeightClassMedium)
                   pointSize:pointSize
              referenceWidth:0];
}

@end
