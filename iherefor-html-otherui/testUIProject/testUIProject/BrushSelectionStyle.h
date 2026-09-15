//
//  BrushSelectionStyle.h
//  testUIProject
//
//  Design tokens, font resolution and the proportional-closure helpers for the
//  Lanhu "笔刷" (Brush) design (image_id cf7f9412-93ae-4081-ac78-ce4863faa1e7).
//
//  Constraint contract ("size fixed, position relative to parent"):
//  the Lanhu canvas is a fixed 393x852 board mapped onto the window with the
//  `fit` policy (one uniform scale, centred). Everything drawn inside that canvas
//  is expressed as a ratio of its **direct parent view**, so the whole board keeps
//  the design's own proportions; the canvas itself closes its height on its own
//  width through the design aspect ratio, which is what makes the scale uniform.
//  Control-intrinsic quantities (font sizes, the 32pt icon, text advance widths,
//  corner radii, border widths, hit areas) stay at their literal design values and
//  never take part in the ratio closure.
//
//  Negative design offsets are legal: a child may sit before its parent's leading
//  or top edge. The Pastel card's tip layer does exactly that (-11pt against a
//  49pt parent, from `index.css` `.image_2 { margin: -11px ... }`), so the closure
//  hangs the spacer off the parent's leading/top edge instead of growing from it.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// Lanhu canvas size of the "笔刷" design (index.css `.page`).
extern const CGFloat kBrushSelectionCanvasWidth;      // 393
extern const CGFloat kBrushSelectionCanvasHeight;     // 852
extern const CGFloat kBrushSelectionCanvasAspectRatio; // height / width

/// What happens to the child's width and height.
typedef NS_ENUM(NSInteger, BrushSelectionClosureSize) {
    /// width/height = parent size x design ratio (containers, cards, decorations).
    BrushSelectionClosureSizeProportional = 0,
    /// Width/height left to intrinsic content size (text, icons), so the type
    /// scale and hit areas never change with the screen.
    BrushSelectionClosureSizeIntrinsic = 1,
};

/// Which edge the child's x position is measured from.
typedef NS_ENUM(NSInteger, BrushSelectionClosureAnchor) {
    BrushSelectionClosureAnchorLeading = 0,
    BrushSelectionClosureAnchorTrailing = 1,
};

@interface BrushSelectionStyle : NSObject

#pragma mark - Proportional closure (the only positioning entry point)

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize;

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(BrushSelectionClosureSize)sizeMode
                                       anchor:(BrushSelectionClosureAnchor)anchor;

/// Uniform `fit` closure for the root canvas: width to the container, height from
/// the canvas width through the design aspect ratio, centred on both axes.
+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container;

/// Logs the multiplier budget for the run evidence.
+ (void)logClosureCounters;

#pragma mark - Colour tokens (from index.css computed values)

+ (UIColor *)pageBackgroundColor;      ///< rgba(241,240,242) #F1F0F2
+ (UIColor *)cardBorderColor;          ///< rgba(222,222,222) #DEDEDE
+ (UIColor *)primaryTextColor;         ///< rgba(22,22,22) #161616
+ (UIColor *)skipTextColor;            ///< rgba(154,154,154) #9A9A9A
+ (UIColor *)progressTrackColor;       ///< rgba(22,22,22,0.2)
+ (UIColor *)progressFillColor;        ///< rgba(22,22,22,1)
+ (UIColor *)onCtaTextColor;           ///< #FFFFFF

#pragma mark - Typography

+ (UIFont *)headlineFont;     ///< Avenir-Black 24
+ (UIFont *)cardTitleFont;    ///< PingFang TC Semibold 16
+ (UIFont *)ctaFont;          ///< Avenir-Heavy 16
+ (UIFont *)skipFont;         ///< Avenir-Medium 14

/// Paragraph style reproducing the CSS `line-height` of a text style.
+ (NSParagraphStyle *)paragraphStyleWithLineHeight:(CGFloat)lineHeight;

@end

NS_ASSUME_NONNULL_END
