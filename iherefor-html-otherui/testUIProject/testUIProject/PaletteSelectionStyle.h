//
//  PaletteSelectionStyle.h
//  testUIProject
//
//  Design tokens, font resolution and the proportional-closure helpers for the
//  Lanhu "色板" (Palette) design (image_id c5e17728-2b7d-4d52-b5a6-3e8a710ec9f6).
//
//  Layout contract ("size fixed, position relative to parent"): the Lanhu canvas
//  is a fixed 393x852 board mapped onto the window with the `fit` policy (one
//  uniform scale, centred). Everything drawn inside that canvas is expressed as a
//  ratio of its **direct parent view**; control-intrinsic quantities (font sizes,
//  corner radii, border widths) stay at their literal design values.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

extern const CGFloat kPaletteCanvasWidth;       // 393
extern const CGFloat kPaletteCanvasHeight;      // 852
extern const CGFloat kPaletteCanvasAspectRatio; // height / width

typedef NS_ENUM(NSInteger, PaletteClosureSize) {
    PaletteClosureSizeProportional = 0,
    PaletteClosureSizeIntrinsic = 1,
};

typedef NS_ENUM(NSInteger, PaletteClosureAnchor) {
    PaletteClosureAnchorLeading = 0,
    PaletteClosureAnchorTrailing = 1,
};

@interface PaletteSelectionStyle : NSObject

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize;

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(PaletteClosureSize)sizeMode
                                       anchor:(PaletteClosureAnchor)anchor;

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container;

/// Uniform `fit` closure with an explicit aspect ratio (height/width).
+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container
                                 aspectRatio:(CGFloat)aspectRatio;

+ (void)logClosureCounters;

#pragma mark - Colour tokens (index.css computed values)

+ (UIColor *)pageBackgroundColor;   ///< rgba(241,240,242) #F1F0F2
+ (UIColor *)cardBackgroundColor;   ///< rgba(251,251,251) #FBFBFB
+ (UIColor *)cardBorderColor;       ///< rgba(222,222,222) #DEDEDE
+ (UIColor *)selectedBorderColor;   ///< rgba(89,87,255)  #5957FF
+ (UIColor *)ctaBackgroundColor;    ///< rgba(89,87,255)  #5957FF
+ (UIColor *)primaryTextColor;      ///< rgba(22,22,22)   #161616
+ (UIColor *)cardTitleTextColor;    ///< rgba(152,151,149) #989795
+ (UIColor *)skipTextColor;         ///< rgba(154,154,154) #9A9A9A
+ (UIColor *)onCtaTextColor;        ///< #FFFFFF
+ (UIColor *)progressTrackColor;    ///< rgba(22,22,22,0.2)
+ (UIColor *)progressFillColor;     ///< rgba(22,22,22,1)

#pragma mark - Typography

+ (UIFont *)headlineFont;    ///< Avenir-Black 24
+ (UIFont *)cardTitleFont;   ///< Avenir-Medium 14
+ (UIFont *)skipFont;        ///< Avenir-Medium 14
+ (UIFont *)ctaFont;         ///< Avenir-Heavy 16
+ (UIFont *)statusFont;      ///< PingFangSC-Semibold 14

+ (NSParagraphStyle *)paragraphStyleWithLineHeight:(CGFloat)lineHeight;

#pragma mark - Image assets

+ (nullable UIImage *)imageNamed:(NSString *)name;

@end

NS_ASSUME_NONNULL_END
