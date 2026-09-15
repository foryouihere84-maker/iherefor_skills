//
//  AgeSelectionStyle.m
//  testUIProject
//

#import "AgeSelectionStyle.h"

const CGFloat kAgeSelectionCanvasWidth = 393.0;
const CGFloat kAgeSelectionCanvasHeight = 852.0;
const CGFloat kAgeSelectionCanvasAspectRatio = 852.0 / 393.0;

/// Counts of the proportional primitives the page actually installed, logged once per
/// run so the layout-proportions check has App-side evidence.
static NSUInteger kAgeSelectionMultiplierCount = 0;
static NSUInteger kAgeSelectionPinCount = 0;
static NSUInteger kAgeSelectionSpacerGuideCount = 0;

@implementation AgeSelectionStyle

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize {
    return [self closeChild:child
                     parent:parent
                designFrame:designFrame
           parentDesignSize:parentDesignSize
                   sizeMode:AgeSelectionClosureSizeProportional
                     anchor:AgeSelectionClosureAnchorLeading];
}

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(AgeSelectionClosureSize)sizeMode
                                       anchor:(AgeSelectionClosureAnchor)anchor {
    NSParameterAssert(parentDesignSize.width > 0 && parentDesignSize.height > 0);
    child.translatesAutoresizingMaskIntoConstraints = NO;

    NSMutableArray<NSLayoutConstraint *> *constraints = [NSMutableArray array];

    // --- x axis ---
    if (sizeMode == AgeSelectionClosureSizeProportional) {
        CGFloat wRatio = designFrame.size.width / parentDesignSize.width;
        if (fabs(wRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:1.0 constant:0.0]];
            ++kAgeSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:wRatio constant:0.0]];
            ++kAgeSelectionMultiplierCount;
        }
    }

    if (anchor == AgeSelectionClosureAnchorTrailing) {
        CGFloat trailingInset = parentDesignSize.width - (designFrame.origin.x + designFrame.size.width);
        CGFloat insetRatio = trailingInset / parentDesignSize.width;
        if (fabs(insetRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0 constant:0.0]];
            ++kAgeSelectionPinCount;
        } else {
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent edgeRatio:insetRatio atTrail:YES];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeLeading
                                                               multiplier:1.0 constant:0.0]];
            ++kAgeSelectionMultiplierCount;
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
            ++kAgeSelectionPinCount;
        } else {
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent edgeRatio:xRatio atTrail:NO];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0 constant:0.0]];
            ++kAgeSelectionMultiplierCount;
        }
    }

    // --- y axis ---
    if (sizeMode == AgeSelectionClosureSizeProportional) {
        CGFloat hRatio = designFrame.size.height / parentDesignSize.height;
        if (fabs(hRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:1.0 constant:0.0]];
            ++kAgeSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:hRatio constant:0.0]];
            ++kAgeSelectionMultiplierCount;
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
        ++kAgeSelectionPinCount;
    } else {
        UILayoutGuide *spacer = [self verticalSpacerInParent:parent offsetRatio:yRatio];
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:spacer
                                                            attribute:NSLayoutAttributeBottom
                                                           multiplier:1.0 constant:0.0]];
        ++kAgeSelectionMultiplierCount;
    }

    return constraints;
}

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container {
    canvas.translatesAutoresizingMaskIntoConstraints = NO;
    // The Lanhu design is a fixed 393x852 board mapped onto the device viewport
    // with the `fit` policy (one uniform scale + centring), exactly like the
    // baseline-viewport.css used for the HTML reference. width = container x 1,
    // height = canvas width x aspect ratio (the single legal cross-axis size
    // pairing). This makes the page fill the device width while children keep
    // their proportional positions relative to this page-sized parent.
    ++kAgeSelectionMultiplierCount;
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
                                    multiplier:kAgeSelectionCanvasAspectRatio constant:0.0],
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
          (unsigned long)kAgeSelectionMultiplierCount,
          (unsigned long)kAgeSelectionPinCount,
          (unsigned long)kAgeSelectionSpacerGuideCount);
}

#pragma mark - Spacer guides

+ (UILayoutGuide *)horizontalSpacerInParent:(UIView *)parent
                                  edgeRatio:(CGFloat)edgeRatio
                                    atTrail:(BOOL)atTrail {
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kAgeSelectionSpacerGuideCount;

    NSLayoutAttribute ownEdge = atTrail ? NSLayoutAttributeTrailing : NSLayoutAttributeLeading;
    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeWidth
                                   multiplier:edgeRatio constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:ownEdge
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:ownEdge
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
    return spacer;
}

+ (UILayoutGuide *)verticalSpacerInParent:(UIView *)parent
                              offsetRatio:(CGFloat)offsetRatio {
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kAgeSelectionSpacerGuideCount;

    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeHeight
                                   multiplier:offsetRatio constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeTop
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

+ (UIColor *)cardSelectedBorderColor {
    return [UIColor colorWithRed:89 / 255.0 green:87 / 255.0 blue:255 / 255.0 alpha:1];
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

static UIFont *AgeFont(NSString *postScriptName, CGFloat size) {
    UIFont *font = [UIFont fontWithName:postScriptName size:size];
    return font ?: [UIFont systemFontOfSize:size];
}

+ (UIFont *)headlineFont {
    return AgeFont(@"Avenir-Black", 24.0);
}

+ (UIFont *)optionFont {
    return AgeFont(@"Avenir-Medium", 18.0);
}

+ (UIFont *)ctaFont {
    return AgeFont(@"Avenir-Heavy", 16.0);
}

+ (UIFont *)skipFont {
    return AgeFont(@"Avenir-Medium", 14.0);
}

+ (UIFont *)emojiFont {
    UIFont *font = [UIFont fontWithName:@"AppleColorEmoji" size:18.0];
    return font ?: [UIFont systemFontOfSize:18.0];
}

@end
