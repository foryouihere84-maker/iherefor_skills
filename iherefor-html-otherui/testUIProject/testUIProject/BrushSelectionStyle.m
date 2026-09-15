//
//  BrushSelectionStyle.m
//  testUIProject
//

#import "BrushSelectionStyle.h"

const CGFloat kBrushSelectionCanvasWidth = 393.0;
const CGFloat kBrushSelectionCanvasHeight = 852.0;
const CGFloat kBrushSelectionCanvasAspectRatio = 852.0 / 393.0;

/// Counts of the layout primitives the page actually installed, logged once per run
/// so the layout-proportions check has App-side evidence.
static NSUInteger kBrushSelectionMultiplierCount = 0;
static NSUInteger kBrushSelectionPinCount = 0;
static NSUInteger kBrushSelectionSpacerGuideCount = 0;

@implementation BrushSelectionStyle

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize {
    return [self closeChild:child
                     parent:parent
                designFrame:designFrame
           parentDesignSize:parentDesignSize
                   sizeMode:BrushSelectionClosureSizeProportional
                     anchor:BrushSelectionClosureAnchorLeading];
}

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(BrushSelectionClosureSize)sizeMode
                                       anchor:(BrushSelectionClosureAnchor)anchor {
    NSParameterAssert(parentDesignSize.width > 0 && parentDesignSize.height > 0);
    child.translatesAutoresizingMaskIntoConstraints = NO;

    NSMutableArray<NSLayoutConstraint *> *constraints = [NSMutableArray array];

    // --- x axis ---
    if (sizeMode == BrushSelectionClosureSizeProportional) {
        CGFloat wRatio = designFrame.size.width / parentDesignSize.width;
        if (fabs(wRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:wRatio constant:0.0]];
            ++kBrushSelectionMultiplierCount;
        }
    }

    if (anchor == BrushSelectionClosureAnchorTrailing) {
        CGFloat trailingInset = parentDesignSize.width - (designFrame.origin.x + designFrame.size.width);
        CGFloat insetRatio = trailingInset / parentDesignSize.width;
        if (fabs(insetRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionPinCount;
        } else {
            NSLayoutAttribute attach = NSLayoutAttributeNotAnAttribute;
            UILayoutGuide *spacer = [self trailingSpacerInParent:parent
                                                      insetRatio:insetRatio
                                                     childAttach:&attach];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:attach
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionMultiplierCount;
        }
    } else {
        CGFloat xRatio = designFrame.origin.x / parentDesignSize.width;
        if (fabs(xRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeLeading
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionPinCount;
        } else {
            NSLayoutAttribute attach = NSLayoutAttributeNotAnAttribute;
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent
                                                       offsetRatio:xRatio
                                                        childAttach:&attach];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:attach
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionMultiplierCount;
        }
    }

    // --- y axis ---
    if (sizeMode == BrushSelectionClosureSizeProportional) {
        CGFloat hRatio = designFrame.size.height / parentDesignSize.height;
        if (fabs(hRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:1.0 constant:0.0]];
            ++kBrushSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:hRatio constant:0.0]];
            ++kBrushSelectionMultiplierCount;
        }
    }

    CGFloat yRatio = designFrame.origin.y / parentDesignSize.height;
    if (fabs(yRatio) < 1e-9) {
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:parent
                                                            attribute:NSLayoutAttributeTop
                                                           multiplier:1.0 constant:0.0]];
        ++kBrushSelectionPinCount;
    } else {
        NSLayoutAttribute attach = NSLayoutAttributeNotAnAttribute;
        UILayoutGuide *spacer = [self verticalSpacerInParent:parent
                                                 offsetRatio:yRatio
                                                  childAttach:&attach];
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:spacer
                                                            attribute:attach
                                                           multiplier:1.0 constant:0.0]];
        ++kBrushSelectionMultiplierCount;
    }

    return constraints;
}

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container {
    canvas.translatesAutoresizingMaskIntoConstraints = NO;
    // The Lanhu design is a fixed 393x852 board mapped onto the device viewport with
    // the `fit` policy (one uniform scale + centring), exactly like the
    // baseline-viewport.css used for the HTML reference. width = container x 1,
    // height = canvas width x design aspect ratio: the single legal cross-axis
    // pairing, and the reason both axes share one scale factor.
    ++kBrushSelectionMultiplierCount;
    return @[
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeWidth
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeWidth
                                    multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeHeight
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:canvas
                                     attribute:NSLayoutAttributeWidth
                                    multiplier:kBrushSelectionCanvasAspectRatio constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeCenterX
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeCenterX
                                    multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeCenterY
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeCenterY
                                    multiplier:1.0 constant:0.0],
    ];
}

+ (void)logClosureCounters {
    NSLog(@"IHEREFOR_LAYOUT_PRIMITIVES multipliers=%lu pins=%lu spacerGuides=%lu",
          (unsigned long)kBrushSelectionMultiplierCount,
          (unsigned long)kBrushSelectionPinCount,
          (unsigned long)kBrushSelectionSpacerGuideCount);
}

#pragma mark - Spacer guides
//
// A spacer is a 1pt-thin layout guide carrying the *offset* between the parent's
// leading/top edge and the child's edge. Its length is |ratio| x parent size, so
// the multiplier stays non-negative even when the offset is negative; the sign is
// expressed by which end of the spacer is pinned to the parent's origin edge and
// which end the child attaches to. That keeps `multiplier:` on the dimension
// constraint always legal while still allowing a child to sit outside its parent
// (the Pastel tip layer, -11pt against a 49pt parent).

+ (UILayoutGuide *)makeSpacerInParent:(UIView *)parent {
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kBrushSelectionSpacerGuideCount;
    return spacer;
}

+ (UILayoutGuide *)horizontalSpacerInParent:(UIView *)parent
                                offsetRatio:(CGFloat)offsetRatio
                                 childAttach:(NSLayoutAttribute *)childAttach {
    UILayoutGuide *spacer = [self makeSpacerInParent:parent];
    BOOL forward = offsetRatio >= 0;

    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeWidth
                                   multiplier:fabs(offsetRatio) constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:forward ? NSLayoutAttributeLeading
                                                      : NSLayoutAttributeTrailing
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeLeading
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeTop
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeTop
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:nil
                                    attribute:NSLayoutAttributeNotAnAttribute
                                   multiplier:1.0 constant:1.0],
    ]];

    if (childAttach) {
        *childAttach = forward ? NSLayoutAttributeTrailing : NSLayoutAttributeLeading;
    }
    return spacer;
}

+ (UILayoutGuide *)trailingSpacerInParent:(UIView *)parent
                               insetRatio:(CGFloat)insetRatio
                              childAttach:(NSLayoutAttribute *)childAttach {
    UILayoutGuide *spacer = [self makeSpacerInParent:parent];
    BOOL inside = insetRatio >= 0; // positive inset = the child stops short of the parent's trailing edge

    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeWidth
                                   multiplier:fabs(insetRatio) constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:inside ? NSLayoutAttributeTrailing
                                                     : NSLayoutAttributeLeading
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeTrailing
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeTop
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeTop
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:nil
                                    attribute:NSLayoutAttributeNotAnAttribute
                                   multiplier:1.0 constant:1.0],
    ]];

    if (childAttach) {
        *childAttach = inside ? NSLayoutAttributeLeading : NSLayoutAttributeTrailing;
    }
    return spacer;
}

+ (UILayoutGuide *)verticalSpacerInParent:(UIView *)parent
                              offsetRatio:(CGFloat)offsetRatio
                               childAttach:(NSLayoutAttribute *)childAttach {
    UILayoutGuide *spacer = [self makeSpacerInParent:parent];
    BOOL forward = offsetRatio >= 0;

    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeHeight
                                   multiplier:fabs(offsetRatio) constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:forward ? NSLayoutAttributeTop
                                                      : NSLayoutAttributeBottom
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeTop
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeLeading
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeLeading
                                   multiplier:1.0 constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:nil
                                    attribute:NSLayoutAttributeNotAnAttribute
                                   multiplier:1.0 constant:1.0],
    ]];

    if (childAttach) {
        *childAttach = forward ? NSLayoutAttributeBottom : NSLayoutAttributeTop;
    }
    return spacer;
}

#pragma mark - Colour tokens

+ (UIColor *)pageBackgroundColor {
    return [UIColor colorWithRed:241 / 255.0 green:240 / 255.0 blue:242 / 255.0 alpha:1];
}

+ (UIColor *)cardBorderColor {
    return [UIColor colorWithRed:222 / 255.0 green:222 / 255.0 blue:222 / 255.0 alpha:1];
}

+ (UIColor *)primaryTextColor {
    return [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 blue:22 / 255.0 alpha:1];
}

+ (UIColor *)skipTextColor {
    return [UIColor colorWithRed:154 / 255.0 green:154 / 255.0 blue:154 / 255.0 alpha:1];
}

+ (UIColor *)progressTrackColor {
    return [UIColor colorWithWhite:22 / 255.0 alpha:0.2];
}

+ (UIColor *)progressFillColor {
    return [UIColor colorWithWhite:22 / 255.0 alpha:1];
}

+ (UIColor *)onCtaTextColor {
    return UIColor.whiteColor;
}

#pragma mark - Typography

static UIFont *BrushFont(NSString *postScriptName, CGFloat size, UIFontWeight fallbackWeight) {
    UIFont *font = [UIFont fontWithName:postScriptName size:size];
    return font ?: [UIFont systemFontOfSize:size weight:fallbackWeight];
}

+ (UIFont *)headlineFont {
    return BrushFont(@"Avenir-Black", 24.0, UIFontWeightHeavy);
}

+ (UIFont *)cardTitleFont {
    // index.css declares `PingFangTC-Semibold`; on iOS that PostScript name resolves
    // directly, and the fallback keeps the same optical weight if it ever does not.
    return BrushFont(@"PingFangTC-Semibold", 16.0, UIFontWeightSemibold);
}

+ (UIFont *)ctaFont {
    return BrushFont(@"Avenir-Heavy", 16.0, UIFontWeightHeavy);
}

+ (UIFont *)skipFont {
    return BrushFont(@"Avenir-Medium", 14.0, UIFontWeightMedium);
}

+ (NSParagraphStyle *)paragraphStyleWithLineHeight:(CGFloat)lineHeight {
    NSMutableParagraphStyle *style = [[NSMutableParagraphStyle alloc] init];
    style.minimumLineHeight = lineHeight;
    style.maximumLineHeight = lineHeight;
    return style;
}

@end
