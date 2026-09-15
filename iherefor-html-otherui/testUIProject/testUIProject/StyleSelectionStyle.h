//
//  StyleSelectionStyle.h
//  testUIProject
//
//  Design tokens and the proportional-closure helpers shared by every Style selection
//  region view.
//
//  Sizing / positioning contract for this page (references/sizing-and-positioning.md):
//    * positions are constraints relative to the DIRECT PARENT view, so a relation
//      re-solves on any screen instead of freezing the 402x874 probe device;
//    * a relation that is genuinely "flush against the parent" is written as a plain
//      pin, not as a 0-valued ratio;
//    * text advance width, line height, font size, corner radii, stroke widths and the
//      >=44pt hit area are design constants and never scale.
//
//  Why the closures below use UILayoutGuide instead of a single multiplier:
//  CoreAutoLayout rejects any *position-to-size* pairing. Writing the obvious
//  `child.leading = parent.width * ratio` or `child.centerY = parent.height * 0.5`
//  raises "Invalid pairing of layout attributes" at constraint-creation time, which
//  crash-launches before the first frame. The legal vocabulary is:
//      same-attribute      (leading-leading, top-top, width-width, height-height, ...)
//      position-to-position across edges (leading-trailing, top-bottom)
//      size-to-size across axes (height-width)  <- only as a single-view aspect ratio
//  So a proportional offset is expressed as a spacer guide whose WIDTH (or HEIGHT) is
//  the parent's size times the design ratio, anchored at the parent's leading (or top)
//  edge; the child then pins to the guide's far edge. That is a genuine multiplier on a
//  real dimension, so it re-solves per device rather than baking in a point value.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// Lanhu canvas size of the "风格" design (index.css `.page`).
extern const CGFloat kStyleSelectionCanvasWidth;
extern const CGFloat kStyleSelectionCanvasHeight;

/// Aspect ratio of the Lanhu canvas (height / width). The page is a fixed,
/// non-scrolling canvas, so it is mapped onto the screen with the `fit` policy: one
/// uniform scale plus centring, i.e. no vertical stretch.
extern const CGFloat kStyleSelectionCanvasAspectRatio;

/// What happens to the child's width and height.
typedef NS_ENUM(NSInteger, StyleSelectionClosureSize) {
    /// width/height = parent size x design ratio. For containers and decorative areas.
    StyleSelectionClosureSizeProportional = 0,
    /// Width and height are left to the view (UILabel/UIImageView intrinsic size), so
    /// the type scale and the >=44pt hit area never change with the screen.
    StyleSelectionClosureSizeIntrinsic = 1,
};

/// Which edge the child's x position is measured from.
typedef NS_ENUM(NSInteger, StyleSelectionClosureAnchor) {
    /// Positioned from the parent's leading edge (default for LTR layouts).
    StyleSelectionClosureAnchorLeading = 0,
    /// Positioned from the parent's trailing edge, for right-aligned content.
    StyleSelectionClosureAnchorTrailing = 1,
};

@interface StyleSelectionStyle : NSObject

#pragma mark - Proportional closure (the only positioning entry point)

/// Closes `child` onto its DIRECT PARENT using multipliers derived from the Lanhu
/// design frames. Every multiplier is `childDesignValue / parentDesignValue`.
///
/// The caller must already have added `child` as a direct subview of `parent`, and
/// must not separately constrain the attributes this sets.
///
/// A design offset of 0 is written as a plain pin to the parent's leading/top edge:
/// "flush against the parent" is not a proportion, and a 0-value ratio would read as
/// proportional while behaving as a constant.
+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize;

/// Full form: lets the caller keep text/artwork at their intrinsic size and/or anchor
/// the child to the parent's trailing edge.
+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(StyleSelectionClosureSize)sizeMode
                                       anchor:(StyleSelectionClosureAnchor)anchor;

/// Uniform `fit` closure for the root canvas: the height is derived from the canvas's
/// own width through the design aspect ratio, so both axes share one scale factor and
/// the content is never stretched. Anchoring the height to the container's HEIGHT
/// instead would silently turn `fit` into `fill`.
+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container;

/// Logs the multiplier budget so the run evidence can show how many proportional
/// relations the page actually contains.
+ (void)logClosureCounters;

#pragma mark - Colour tokens (index.css computed values)

+ (UIColor *)pageBackgroundColor;
+ (UIColor *)headlineTextColor;
+ (UIColor *)skipTextColor;
+ (UIColor *)cardLabelTextColor;
+ (UIColor *)progressTrackColor;
+ (UIColor *)progressFillColor;
+ (UIColor *)selectionRingColor;

#pragma mark - Design constants (never scaled)

+ (CGFloat)selectionRingBorderWidth;      ///< .box_3 border: 1.5px
+ (CGFloat)selectionRingCornerRadius;     ///< .box_3 border-radius: 12px
+ (CGFloat)continueButtonCornerRadius;    ///< .text-wrapper_11 border-radius: 28px
+ (CGFloat)progressCornerRadius;          ///< .group_3 / .box_2 border-radius: 3px
+ (CGFloat)minimumHitSize;                ///< 44pt platform minimum, never scaled
+ (CGFloat)navBackHitSize;                ///< 44pt hit box grown around the 32pt icon

#pragma mark - Typography

/// The CSS weight class, i.e. the role the Lanhu CSS assigns inside index.css.
typedef NS_ENUM(NSInteger, StyleSelectionFontWeightClass) {
    StyleSelectionFontWeightClassBlack = 0,  ///< AvenirLT-Black, CSS family AvenirLT-Black
    StyleSelectionFontWeightClassMedium = 1, ///< AvenirLT-Medium, CSS weight 500
    StyleSelectionFontWeightClassSystem = 2, ///< PingFangSC-Semibold (the ？ mark)
};

/// index.css declares AvenirLT-Black / AvenirLT-Medium, neither of which is installed
/// (the export ships zero @font-face rules), so the reference render is itself a
/// fallback. Instead of guessing a substitute, pick the installed face whose measured
/// advance width best matches the reference render and nudge the glyph size to close
/// the remainder. Bounds are [0.80, 1.20] so a bad candidate cannot silently change
/// the type hierarchy. Every pick is logged as IHEREFOR_FONT_RESOLVED.
///
/// `pointSize` is always the CSS design size and `referenceWidth` the design-space
/// advance width, so a wider screen never changes the type scale.
+ (UIFont *)fontForText:(NSString *)text
                  class:(StyleSelectionFontWeightClass)weightClass
              pointSize:(CGFloat)pointSize
         referenceWidth:(CGFloat)referenceWidth;

/// Design-space reference advance widths, measured from reference/page-facts.json.
+ (CGFloat)referenceWidthForStyleName:(NSString *)styleName;
+ (CGFloat)pointSizeForStyleName:(NSString *)styleName;

/// Logs which installed faces land closest to a reference advance width.
+ (void)logFontCandidatesForText:(NSString *)text
                       pointSize:(CGFloat)pointSize
                  referenceWidth:(CGFloat)referenceWidth;

@end

NS_ASSUME_NONNULL_END
