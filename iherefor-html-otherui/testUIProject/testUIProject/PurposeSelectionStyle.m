//
//  PurposeSelectionStyle.m
//  testUIProject
//

#import "PurposeSelectionStyle.h"

const CGFloat kPurposeCanvasWidth = 393.0;
const CGFloat kPurposeCanvasHeight = 852.0;
const CGFloat kPurposeCanvasAspectRatio = 852.0 / 393.0;

static NSUInteger kPurposeMultiplierCount = 0;
static NSUInteger kPurposePinCount = 0;
static NSUInteger kPurposeSpacerGuideCount = 0;

@implementation PurposeSelectionStyle

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize {
    return [self closeChild:child
                     parent:parent
                designFrame:designFrame
           parentDesignSize:parentDesignSize
                   sizeMode:PurposeClosureSizeProportional
                     anchor:PurposeClosureAnchorLeading];
}

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(PurposeClosureSize)sizeMode
                                       anchor:(PurposeClosureAnchor)anchor {
    NSParameterAssert(parentDesignSize.width > 0 && parentDesignSize.height > 0);
    child.translatesAutoresizingMaskIntoConstraints = NO;

    NSMutableArray<NSLayoutConstraint *> *constraints = [NSMutableArray array];

    if (sizeMode == PurposeClosureSizeProportional) {
        CGFloat wRatio = designFrame.size.width / parentDesignSize.width;
        if (fabs(wRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:1.0 constant:0.0]];
            ++kPurposePinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:wRatio constant:0.0]];
            ++kPurposeMultiplierCount;
        }
    }

    if (anchor == PurposeClosureAnchorTrailing) {
        CGFloat trailingInset = parentDesignSize.width - (designFrame.origin.x + designFrame.size.width);
        CGFloat insetRatio = trailingInset / parentDesignSize.width;
        if (fabs(insetRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0 constant:0.0]];
            ++kPurposePinCount;
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
            ++kPurposeMultiplierCount;
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
            ++kPurposePinCount;
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
            ++kPurposeMultiplierCount;
        }
    }

    if (sizeMode == PurposeClosureSizeProportional) {
        CGFloat hRatio = designFrame.size.height / parentDesignSize.height;
        if (fabs(hRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:1.0 constant:0.0]];
            ++kPurposePinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:hRatio constant:0.0]];
            ++kPurposeMultiplierCount;
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
        ++kPurposePinCount;
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
        ++kPurposeMultiplierCount;
    }

    return constraints;
}

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container {
    return [self fitCanvas:canvas insideView:container aspectRatio:kPurposeCanvasAspectRatio];
}

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container
                                 aspectRatio:(CGFloat)aspectRatio {
    canvas.translatesAutoresizingMaskIntoConstraints = NO;
    ++kPurposeMultiplierCount;
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
                                    multiplier:aspectRatio constant:0.0],
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
          (unsigned long)kPurposeMultiplierCount,
          (unsigned long)kPurposePinCount,
          (unsigned long)kPurposeSpacerGuideCount);
}

#pragma mark - Spacer guides

+ (UILayoutGuide *)makeSpacerInParent:(UIView *)parent {
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kPurposeSpacerGuideCount;
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
    BOOL inside = insetRatio >= 0;

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

+ (UIColor *)cardBackgroundColor {
    return [UIColor colorWithRed:251 / 255.0 green:251 / 255.0 blue:251 / 255.0 alpha:1];
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

+ (UIColor *)onCtaTextColor {
    return UIColor.whiteColor;
}

#pragma mark - Typography

static UIFont *PurposeFont(NSString *postScriptName, CGFloat size, UIFontWeight fallbackWeight) {
    UIFont *font = [UIFont fontWithName:postScriptName size:size];
    return font ?: [UIFont systemFontOfSize:size weight:fallbackWeight];
}

+ (UIFont *)headlineFont {
    return PurposeFont(@"Avenir-Black", 24.0, UIFontWeightHeavy);
}

+ (UIFont *)optionFont {
    return PurposeFont(@"Avenir-Medium", 18.0, UIFontWeightMedium);
}

+ (UIFont *)ctaFont {
    return PurposeFont(@"Avenir-Heavy", 16.0, UIFontWeightHeavy);
}

+ (UIFont *)skipFont {
    return PurposeFont(@"Avenir-Medium", 14.0, UIFontWeightMedium);
}

+ (UIFont *)headlineFontIpad {
    return PurposeFont(@"Avenir-Black", 30.0, UIFontWeightHeavy);
}

+ (UIFont *)skipFontIpad {
    return PurposeFont(@"Avenir-Medium", 18.0, UIFontWeightMedium);
}

+ (UIFont *)ctaFontIpad {
    // iPad CSS `.text_17 { font-family: PingFangSC-Medium; font-size: 20px }`.
    return PurposeFont(@"PingFangSC-Medium", 20.0, UIFontWeightMedium);
}

+ (NSParagraphStyle *)paragraphStyleWithLineHeight:(CGFloat)lineHeight {
    NSMutableParagraphStyle *style = [[NSMutableParagraphStyle alloc] init];
    style.minimumLineHeight = lineHeight;
    style.maximumLineHeight = lineHeight;
    return style;
}

@end
