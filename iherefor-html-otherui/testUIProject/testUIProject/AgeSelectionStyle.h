//
//  AgeSelectionStyle.h
//  testUIProject
//
//  Design tokens, font resolution and the proportional-closure helpers for the
//  Lanhu "年龄" (Age) design (image_id daa18fa7-31ee-400a-bbad-fbfebd5a30e0).
//
//  Constraint contract ("size fixed, position relative to parent"): control sizes
//  (card 353x65, CTA 347x56), font sizes, corner radii and border widths are
//  written as literal design values; positions anchor to the direct parent through
//  proportional multiplier guides. A design offset of 0 is expressed as a plain
//  pin (flush to the parent edge), not a zero ratio.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// Lanhu canvas size of the "年龄" design (index.css `.page`).
extern const CGFloat kAgeSelectionCanvasWidth;    // 393
extern const CGFloat kAgeSelectionCanvasHeight;   // 852
extern const CGFloat kAgeSelectionCanvasAspectRatio; // height / width

/// What happens to the child's width and height.
typedef NS_ENUM(NSInteger, AgeSelectionClosureSize) {
    /// width/height = parent size x design ratio (containers and decorative areas).
    AgeSelectionClosureSizeProportional = 0,
    /// Width/height left to intrinsic content size (text/emoji/icon), so the
    /// type scale and hit areas never change with the screen.
    AgeSelectionClosureSizeIntrinsic = 1,
};

/// Which edge the child's x position is measured from.
typedef NS_ENUM(NSInteger, AgeSelectionClosureAnchor) {
    AgeSelectionClosureAnchorLeading = 0,
    AgeSelectionClosureAnchorTrailing = 1,
};

@interface AgeSelectionStyle : NSObject

#pragma mark - Proportional closure (the only positioning entry point)

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize;

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(AgeSelectionClosureSize)sizeMode
                                       anchor:(AgeSelectionClosureAnchor)anchor;

/// Uniform `fit` closure for the root canvas: height derived from the canvas width
/// through the design aspect ratio, so both axes share one scale factor.
+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container;

/// Logs the multiplier budget for the run evidence.
+ (void)logClosureCounters;

#pragma mark - Colour tokens (from index.css computed values)

+ (UIColor *)pageBackgroundColor;      ///< rgba(241,240,242) #F1F0F2
+ (UIColor *)cardBackgroundColor;      ///< rgba(251,251,251) #FBFBFB
+ (UIColor *)cardBorderColor;          ///< rgba(222,222,222) #DEDEDE
+ (UIColor *)cardSelectedBorderColor;  ///< rgba(89,87,255) #5957FF
+ (UIColor *)primaryTextColor;         ///< rgba(22,22,22) #161616
+ (UIColor *)skipTextColor;            ///< rgba(154,154,154) #9A9A9A
+ (UIColor *)progressTrackColor;       ///< rgba(22,22,22,0.2)
+ (UIColor *)progressFillColor;        ///< rgba(22,22,22,1)
+ (UIColor *)onCtaTextColor;           ///< #FFFFFF

#pragma mark - Typography

+ (UIFont *)headlineFont;     ///< Avenir-Black 24
+ (UIFont *)optionFont;       ///< Avenir-Medium 18
+ (UIFont *)ctaFont;          ///< Avenir-Heavy 16
+ (UIFont *)skipFont;         ///< Avenir-Medium 14
+ (UIFont *)emojiFont;        ///< Apple Color Emoji 18

@end

NS_ASSUME_NONNULL_END
