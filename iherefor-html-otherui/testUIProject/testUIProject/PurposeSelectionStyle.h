//
//  PurposeSelectionStyle.h
//  testUIProject
//
//  Design tokens, font resolution and the proportional-closure helpers for the
//  Lanhu "目的" (Purpose) design (image_id cc79645f-0e5a-4cc0-ac76-fd763905e305).
//
//  Layout contract ("size fixed, position relative to parent"): the Lanhu canvas
//  is a fixed 393x852 board mapped onto the window with the `fit` policy (one
//  uniform scale, centred). Everything drawn inside that canvas is expressed as a
//  ratio of its **direct parent view**; control-intrinsic quantities (font sizes,
//  corner radii, border widths) stay at their literal design values.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

extern const CGFloat kPurposeCanvasWidth;       // 393
extern const CGFloat kPurposeCanvasHeight;      // 852
extern const CGFloat kPurposeCanvasAspectRatio; // height / width

typedef NS_ENUM(NSInteger, PurposeClosureSize) {
    PurposeClosureSizeProportional = 0,
    PurposeClosureSizeIntrinsic = 1,
};

typedef NS_ENUM(NSInteger, PurposeClosureAnchor) {
    PurposeClosureAnchorLeading = 0,
    PurposeClosureAnchorTrailing = 1,
};

@interface PurposeSelectionStyle : NSObject

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize;

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(PurposeClosureSize)sizeMode
                                       anchor:(PurposeClosureAnchor)anchor;

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container;

/// Uniform `fit` closure with an explicit aspect ratio (height/width), so the same
/// helper serves both the compact canvas (852/393) and the regular canvas (1080/810).
+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container
                                 aspectRatio:(CGFloat)aspectRatio;

+ (void)logClosureCounters;

#pragma mark - Colour tokens (index.css computed values)

+ (UIColor *)pageBackgroundColor;   ///< rgba(241,240,242) #F1F0F2
+ (UIColor *)cardBackgroundColor;   ///< rgba(251,251,251) #FBFBFB
+ (UIColor *)cardBorderColor;       ///< rgba(222,222,222) #DEDEDE
+ (UIColor *)primaryTextColor;      ///< rgba(22,22,22) #161616
+ (UIColor *)skipTextColor;         ///< rgba(154,154,154) #9A9A9A
+ (UIColor *)onCtaTextColor;        ///< #FFFFFF

#pragma mark - Typography

+ (UIFont *)headlineFont;    ///< Avenir-Black 24
+ (UIFont *)optionFont;      ///< Avenir-Medium 18
+ (UIFont *)ctaFont;         ///< Avenir-Heavy 16
+ (UIFont *)skipFont;        ///< Avenir-Medium 14

/// iPad-board type (目的-iPad uses larger sizes; option X two-spec adaptation).
+ (UIFont *)headlineFontIpad;  ///< Avenir-Black 30
+ (UIFont *)skipFontIpad;      ///< Avenir-Medium 18
+ (UIFont *)ctaFontIpad;       ///< PingFangSC-Medium 20 (iPad CSS uses PingFangSC-Medium)

+ (NSParagraphStyle *)paragraphStyleWithLineHeight:(CGFloat)lineHeight;

@end

NS_ASSUME_NONNULL_END
