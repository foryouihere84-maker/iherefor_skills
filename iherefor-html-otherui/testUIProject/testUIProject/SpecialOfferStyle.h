//
//  SpecialOfferStyle.h
//  testUIProject
//
//  Canvas constants, colour/typography tokens and the coordinate mapper shared by
//  every Special offer region view. Lanhu canvas coordinates are never used
//  directly by a view; they always pass through -mappedRect: / -mappedLength:.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// Lanhu canvas size of the "Special offer" design (index.css `.page`).
extern const CGFloat kSpecialOfferCanvasWidth;
extern const CGFloat kSpecialOfferCanvasHeight;

@interface SpecialOfferStyle : NSObject

/// Real device point size taken at runtime from UIScreen / the root view bounds.
@property(nonatomic, readonly) CGSize deviceSize;

/// scaleX = deviceSize.width / canvasWidth, scaleY = deviceSize.height / canvasHeight.
@property(nonatomic, readonly) CGPoint canvasScale;

+ (instancetype)styleForDeviceSize:(CGSize)deviceSize;

- (CGRect)mappedRect:(CGRect)canvasRect;
- (CGFloat)mappedLength:(CGFloat)canvasLength;

#pragma mark - Colour tokens (from index.css computed values)

+ (UIColor *)pageBackgroundColor;
+ (UIColor *)headlineOrangeColor;
+ (UIColor *)headlineAccentBlueColor;
+ (UIColor *)bodyTextColor;
+ (UIColor *)planTitleColor;
+ (UIColor *)planDetailColor;
+ (UIColor *)footerLinkColor;
+ (UIColor *)badgeVioletColor;
+ (UIColor *)badgeOrangeColor;
+ (UIColor *)onAccentTextColor;

#pragma mark - Typography (measured browser fallback chain)

/// CSS weight class, i.e. the role the Lanhu CSS assigns inside index.css.
typedef NS_ENUM(NSInteger, SpecialOfferFontWeightClass) {
    SpecialOfferFontWeightClassBlack = 0,   ///< AvenirLT-Black / Avenir-Heavy, CSS weight 900
    SpecialOfferFontWeightClassMedium = 1,  ///< AvenirLT-Medium / Avenir-Medium, CSS weight 500
};

/// The CSS names AvenirLT-Black / AvenirLT-Medium / Avenir-Heavy / PingFangSC-*,
/// none of which are installed in the simulator or in the Chromium used for the
/// reference. The reference is therefore itself a fallback render. Rather than
/// guessing a substitute, these helpers pick the installed face whose measured
/// advance width per em best matches the reference render (measured at runtime
/// through ref_* below) and scale the point size so the realised width matches.
/// Every pick is logged as IHEREFOR_FONT_RESOLVED for the run evidence.
+ (UIFont *)fontForText:(NSString *)text
               class:(SpecialOfferFontWeightClass)weightClass
           pointSize:(CGFloat)pointSize
    referenceWidth:(CGFloat)referenceWidth;

/// Reference advance widths measured from the HTML baseline at the 402x874
/// viewport. Source: reference/page-facts.json plus the DOM range measurements
/// recorded in ui-implementation-plan.json -> typography.referenceAdvances.
+ (CGFloat)referenceWidthForStyle:(NSString *)styleName;
+ (CGFloat)pointSizeForStyle:(NSString *)styleName;

/// Maps a CSS font size + weight class back onto the reference metric table so
/// call sites keep stating the CSS size they read from index.css.
+ (NSString *)styleNameForPointSize:(CGFloat)pointSize
                             weight:(UIFontWeight)weight
                        isHeadline:(BOOL)isHeadline;

/// Logs which installed faces are closest to a reference advance-width ratio.
+ (void)logFontCandidatesForText:(NSString *)text
                       pointSize:(CGFloat)pointSize
                  referenceWidth:(CGFloat)referenceWidth;

@end

NS_ASSUME_NONNULL_END
