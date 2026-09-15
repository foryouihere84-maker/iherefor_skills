//
//  StyleSelectionStyle.m
//  testUIProject
//

#import "StyleSelectionStyle.h"

const CGFloat kStyleSelectionCanvasWidth = 393.0;
const CGFloat kStyleSelectionCanvasHeight = 852.0;
const CGFloat kStyleSelectionCanvasAspectRatio = 852.0 / 393.0;

/// Counts of the proportional primitives the page actually installed. Logged once per
/// run so the layout-proportions check has App-side evidence, not just plan-side claims.
static NSUInteger kStyleSelectionMultiplierCount = 0;
static NSUInteger kStyleSelectionPinCount = 0;
static NSUInteger kStyleSelectionSpacerGuideCount = 0;

@implementation StyleSelectionStyle

#pragma mark - Proportional closure

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize {
    return [self closeChild:child
                     parent:parent
                designFrame:designFrame
           parentDesignSize:parentDesignSize
                   sizeMode:StyleSelectionClosureSizeProportional
                     anchor:StyleSelectionClosureAnchorLeading];
}

+ (NSArray<NSLayoutConstraint *> *)closeChild:(UIView *)child
                                       parent:(UIView *)parent
                                  designFrame:(CGRect)designFrame
                             parentDesignSize:(CGSize)parentDesignSize
                                     sizeMode:(StyleSelectionClosureSize)sizeMode
                                       anchor:(StyleSelectionClosureAnchor)anchor {
    NSParameterAssert(parentDesignSize.width > 0 && parentDesignSize.height > 0);
    child.translatesAutoresizingMaskIntoConstraints = NO;

    NSMutableArray<NSLayoutConstraint *> *constraints = [NSMutableArray array];

    // --- x axis ---------------------------------------------------------------
    if (sizeMode == StyleSelectionClosureSizeProportional) {
        CGFloat wRatio = designFrame.size.width / parentDesignSize.width;
        if (fabs(wRatio - 1.0) < 1e-9) {
            // Flush with the parent: a pin, not a proportion.
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeWidth
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeWidth
                                                               multiplier:wRatio
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
        }
    }

    if (anchor == StyleSelectionClosureAnchorTrailing) {
        // Distance from the parent's trailing edge, expressed against the parent's width.
        CGFloat trailingInset = parentDesignSize.width - (designFrame.origin.x + designFrame.size.width);
        CGFloat insetRatio = trailingInset / parentDesignSize.width;
        if (fabs(insetRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionPinCount;
        } else if (insetRatio > 0) {
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent
                                                        edgeRatio:insetRatio
                                                         fromTail:YES];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeLeading
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
        } else {
            // The child overruns the parent's trailing edge (a rounded, stroke-outset or
            // otherwise overhanging frame). A negative inset would ask for a negative
            // width, which Auto Layout cannot satisfy, so the same edge is reached by
            // measuring from the LEADING edge instead: width = parent.width x reach, and
            // reach = 1 - insetRatio is necessarily greater than 1.
            CGFloat reach = (designFrame.origin.x + designFrame.size.width) / parentDesignSize.width;
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent
                                                        edgeRatio:reach
                                                         fromTail:NO];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeTrailing
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
        }
    } else {
        CGFloat xRatio = designFrame.origin.x / parentDesignSize.width;
        if (fabs(xRatio) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeLeading
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionPinCount;
        } else if (xRatio > 0) {
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent
                                                        edgeRatio:xRatio
                                                         fromTail:NO];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeTrailing
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
        } else {
            // The child starts before the parent's leading edge, which is how a 44pt hit
            // target is grown around a smaller control. The offset is measured from the
            // TRAILING edge so the multiplier stays positive:
            //   width = parent.width x (1 - xRatio), and 1 - xRatio > 1.
            UILayoutGuide *spacer = [self horizontalSpacerInParent:parent
                                                        edgeRatio:(1.0 - xRatio)
                                                         fromTail:YES];
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeLeading
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:spacer
                                                                attribute:NSLayoutAttributeLeading
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
            NSLog(@"IHEREFOR_LAYOUT_NOTE region=%@ axis=x reason=negative-leading-offset "
                  @"designX=%.3f parentDesignW=%.3f realisedAs=trailing-anchored-spacer ratio=%.6f",
                  child.accessibilityIdentifier ?: NSStringFromClass(child.class),
                  designFrame.origin.x, parentDesignSize.width, 1.0 - xRatio);
        }
    }

    // --- y axis ---------------------------------------------------------------
    if (sizeMode == StyleSelectionClosureSizeProportional) {
        CGFloat hRatio = designFrame.size.height / parentDesignSize.height;
        if (fabs(hRatio - 1.0) < 1e-9) {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:1.0
                                                                 constant:0.0]];
            ++kStyleSelectionPinCount;
        } else {
            [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                                attribute:NSLayoutAttributeHeight
                                                                relatedBy:NSLayoutRelationEqual
                                                                   toItem:parent
                                                                attribute:NSLayoutAttributeHeight
                                                               multiplier:hRatio
                                                                 constant:0.0]];
            ++kStyleSelectionMultiplierCount;
        }
    }

    CGFloat yRatio = designFrame.origin.y / parentDesignSize.height;
    if (fabs(yRatio) < 1e-9) {
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:parent
                                                            attribute:NSLayoutAttributeTop
                                                           multiplier:1.0
                                                             constant:0.0]];
        ++kStyleSelectionPinCount;
    } else if (yRatio > 0) {
        UILayoutGuide *spacer = [self verticalSpacerInParent:parent
                                                 offsetRatio:yRatio
                                                  fromBottom:NO];
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:spacer
                                                            attribute:NSLayoutAttributeBottom
                                                           multiplier:1.0
                                                                 constant:0.0]];
        ++kStyleSelectionMultiplierCount;
    } else {
        // Same reasoning as the x axis: measured from the BOTTOM edge so the multiplier
        // stays positive (height = parent.height x (1 - yRatio), which exceeds 1).
        UILayoutGuide *spacer = [self verticalSpacerInParent:parent
                                                 offsetRatio:(1.0 - yRatio)
                                                  fromBottom:YES];
        [constraints addObject:[NSLayoutConstraint constraintWithItem:child
                                                            attribute:NSLayoutAttributeTop
                                                            relatedBy:NSLayoutRelationEqual
                                                               toItem:spacer
                                                            attribute:NSLayoutAttributeTop
                                                           multiplier:1.0
                                                                 constant:0.0]];
        ++kStyleSelectionMultiplierCount;
        NSLog(@"IHEREFOR_LAYOUT_NOTE region=%@ axis=y reason=negative-top-offset "
              @"designY=%.3f parentDesignH=%.3f realisedAs=bottom-anchored-spacer ratio=%.6f",
              child.accessibilityIdentifier ?: NSStringFromClass(child.class),
              designFrame.origin.y, parentDesignSize.height, 1.0 - yRatio);
    }

    return constraints;
}

+ (NSArray<NSLayoutConstraint *> *)fitCanvas:(UIView *)canvas
                                  insideView:(UIView *)container {
    canvas.translatesAutoresizingMaskIntoConstraints = NO;
    // width      = container.width x 1
    // height     = canvas.WIDTH x (852/393)   -> one shared scale for both axes (`fit`)
    // centreX/Y  = container's centre          -> equal letterbox bands
    // Pairing note: height-to-width is the single legal cross-axis size pairing, and
    // only as a self-constraint (the standard aspect-ratio idiom).
    ++kStyleSelectionMultiplierCount;
    ++kStyleSelectionMultiplierCount;
    return @[
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeWidth
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeWidth
                                    multiplier:1.0
                                      constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeHeight
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:canvas
                                     attribute:NSLayoutAttributeWidth
                                    multiplier:kStyleSelectionCanvasAspectRatio
                                      constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeCenterX
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeCenterX
                                    multiplier:1.0
                                      constant:0.0],
        [NSLayoutConstraint constraintWithItem:canvas
                                     attribute:NSLayoutAttributeCenterY
                                     relatedBy:NSLayoutRelationEqual
                                        toItem:container
                                     attribute:NSLayoutAttributeCenterY
                                    multiplier:1.0
                                      constant:0.0],
    ];
}

+ (void)logClosureCounters {
    NSLog(@"IHEREFOR_LAYOUT_PRIMITIVES multipliers=%lu pins=%lu spacerGuides=%lu "
          @"note=position-to-size pairings are illegal in CoreAutoLayout; proportional "
          @"offsets are realised as spacer guides whose width/height carries the multiplier",
          (unsigned long)kStyleSelectionMultiplierCount,
          (unsigned long)kStyleSelectionPinCount,
          (unsigned long)kStyleSelectionSpacerGuideCount);
}

#pragma mark - Spacer guides

/// A guide pinned to one of the parent's horizontal edges whose WIDTH is the parent's
/// width times `edgeRatio` (which must be strictly positive, otherwise the width would be
/// unsatisfiable). `fromTail == YES` pins it to the trailing edge, so the guide grows
/// leftwards from there; `NO` pins it to the leading edge.
+ (UILayoutGuide *)horizontalSpacerInParent:(UIView *)parent
                                  edgeRatio:(CGFloat)edgeRatio
                                   fromTail:(BOOL)fromTail {
    NSParameterAssert(edgeRatio > 0.0);
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kStyleSelectionSpacerGuideCount;

    NSLayoutAttribute pinnedEdge = fromTail ? NSLayoutAttributeTrailing : NSLayoutAttributeLeading;
    [NSLayoutConstraint activateConstraints:@[
        // width = parent.width x edgeRatio  -> the multiplier lives on a real dimension
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeWidth
                                   multiplier:edgeRatio
                                     constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:pinnedEdge
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:pinnedEdge
                                   multiplier:1.0
                                     constant:0.0],
        // A guide needs a determinate y too; it is only used for its x extent.
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeTop
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeTop
                                   multiplier:1.0
                                     constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:nil
                                    attribute:NSLayoutAttributeNotAnAttribute
                                   multiplier:1.0
                                     constant:1.0],
    ]];
    return spacer;
}

/// A guide pinned to the parent's top (or bottom) edge whose HEIGHT is the parent's
/// height times `offsetRatio`, which must be strictly positive.
+ (UILayoutGuide *)verticalSpacerInParent:(UIView *)parent
                              offsetRatio:(CGFloat)offsetRatio
                               fromBottom:(BOOL)fromBottom {
    NSParameterAssert(offsetRatio > 0.0);
    UILayoutGuide *spacer = [[UILayoutGuide alloc] init];
    [parent addLayoutGuide:spacer];
    ++kStyleSelectionSpacerGuideCount;

    NSLayoutAttribute pinnedEdge = fromBottom ? NSLayoutAttributeBottom : NSLayoutAttributeTop;
    [NSLayoutConstraint activateConstraints:@[
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeHeight
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeHeight
                                   multiplier:offsetRatio
                                     constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:pinnedEdge
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:pinnedEdge
                                   multiplier:1.0
                                     constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeLeading
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:parent
                                    attribute:NSLayoutAttributeLeading
                                   multiplier:1.0
                                     constant:0.0],
        [NSLayoutConstraint constraintWithItem:spacer
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:nil
                                    attribute:NSLayoutAttributeNotAnAttribute
                                   multiplier:1.0
                                     constant:1.0],
    ]];
    return spacer;
}

#pragma mark - Colour tokens

+ (UIColor *)pageBackgroundColor {
    return [UIColor colorWithRed:241 / 255.0 green:240 / 255.0 blue:242 / 255.0 alpha:1];
}

+ (UIColor *)headlineTextColor {
    return [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 blue:22 / 255.0 alpha:1];
}

+ (UIColor *)skipTextColor {
    return [UIColor colorWithRed:154 / 255.0 green:154 / 255.0 blue:154 / 255.0 alpha:1];
}

+ (UIColor *)cardLabelTextColor {
    return UIColor.whiteColor;
}

+ (UIColor *)progressTrackColor {
    return [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 blue:22 / 255.0 alpha:0.2];
}

+ (UIColor *)progressFillColor {
    return [UIColor colorWithRed:22 / 255.0 green:22 / 255.0 blue:22 / 255.0 alpha:1];
}

+ (UIColor *)selectionRingColor {
    return [UIColor colorWithRed:89 / 255.0 green:87 / 255.0 blue:255 / 255.0 alpha:1];
}

#pragma mark - Design constants

+ (CGFloat)selectionRingBorderWidth { return 1.5; }
+ (CGFloat)selectionRingCornerRadius { return 12.0; }
+ (CGFloat)continueButtonCornerRadius { return 28.0; }
+ (CGFloat)progressCornerRadius { return 3.0; }
+ (CGFloat)minimumHitSize { return 44.0; }
+ (CGFloat)navBackHitSize { return 44.0; }

#pragma mark - Typography

// CSS design size + design-space reference advance width, both read from the frozen
// facts table (reference/page-facts.json) after inverting it through canvas_map.py.
// These are design values: they do not change with the screen.
static NSDictionary<NSString *, NSArray<NSNumber *> *> *StyleSelectionTextMetrics(void) {
    static NSDictionary *metrics = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        metrics = @{
            // Headline referenceWidth is 0: the reference (macOS Chromium) resolves
            // Avenir-Black and PingFangSC-Semibold, both of which exist on iOS, and the
            // text wraps across two lines — a single-line advance width is not a sane
            // match target. A width of 0 tells fontForText to take the preferred face at
            // the design point size and skip glyph scaling.
            @"headlineQuestion": @[@24.0, @0.0],
            @"headlineMark":     @[@24.0, @0.0],
            @"cardLabelAnimal":  @[@18.0, @56.00],
            @"cardLabelManga":   @[@18.0, @56.00],
            @"cardLabelPeople":  @[@18.0, @56.70],
            @"cardLabelCute":    @[@18.0, @39.36],
            @"cardLabelFood":    @[@18.0, @42.72],
            @"cardLabelMandala": @[@18.0, @69.67],
            @"cardLabelFlower":  @[@18.0, @55.69],
            @"cardLabelEasy":    @[@18.0, @37.34],
            @"continueTitle":    @[@16.0, @67.00],
            @"skipTitle":        @[@14.0, @26.97],
        };
    });
    return metrics;
}

+ (CGFloat)referenceWidthForStyleName:(NSString *)styleName {
    NSArray<NSNumber *> *entry = StyleSelectionTextMetrics()[styleName];
    return entry ? entry[1].doubleValue : 0.0;
}

+ (CGFloat)pointSizeForStyleName:(NSString *)styleName {
    NSArray<NSNumber *> *entry = StyleSelectionTextMetrics()[styleName];
    return entry ? entry[0].doubleValue : 0.0;
}

/// Faces that may stand in for the AvenirLT / Avenir family declared by index.css.
static NSArray<NSString *> *StyleSelectionFontCandidates(void) {
    return @[
        @"Avenir-Black", @"Avenir-Heavy", @"Avenir-Medium", @"Avenir-Book", @"Avenir-Light",
        @"AvenirNext-Bold", @"AvenirNext-DemiBold", @"AvenirNext-Medium", @"AvenirNext-Regular",
        @"HelveticaNeue-Bold", @"HelveticaNeue-Medium", @"HelveticaNeue",
        @"Arial-BoldMT", @"ArialMT",
        @"PingFangSC-Semibold", @"PingFangSC-Medium", @"PingFangTC-Semibold", @"PingFangTC-Medium",
        @"HiraginoSans-W8", @"HiraginoSans-W6", @"HiraginoSans-W3",
    ];
}

+ (UIFont *)fontForText:(NSString *)text
                  class:(StyleSelectionFontWeightClass)weightClass
              pointSize:(CGFloat)pointSize
         referenceWidth:(CGFloat)referenceWidth {
    if (pointSize <= 0) {
        return [UIFont systemFontOfSize:1];
    }

    NSArray<NSString *> *preferred;
    switch (weightClass) {
        case StyleSelectionFontWeightClassBlack:
            preferred = @[@"Avenir-Black", @"Avenir-Heavy", @"AvenirNext-Bold",
                          @"HelveticaNeue-Bold", @"Arial-BoldMT"];
            break;
        case StyleSelectionFontWeightClassSystem:
            preferred = @[@"PingFangSC-Semibold", @"PingFangTC-Semibold",
                          @"HiraginoSans-W6", @"AvenirNext-DemiBold"];
            break;
        case StyleSelectionFontWeightClassMedium:
        default:
            preferred = @[@"Avenir-Medium", @"AvenirNext-Medium", @"HelveticaNeue-Medium",
                          @"PingFangSC-Medium", @"ArialMT"];
            break;
    }
    NSArray<NSString *> *candidates = [preferred arrayByAddingObjectsFromArray:StyleSelectionFontCandidates()];

    UIFont *bestFont = nil;
    CGFloat bestDelta = CGFLOAT_MAX;
    CGFloat bestWidth = 0;
    NSMutableSet<NSString *> *seen = [NSMutableSet set];
    for (NSString *face in candidates) {
        if ([seen containsObject:face]) { continue; }
        [seen addObject:face];
        UIFont *font = [UIFont fontWithName:face size:pointSize];
        if (!font) { continue; }
        CGFloat width = [text sizeWithAttributes:@{NSFontAttributeName : font}].width;
        if (width <= 0) { continue; }
        CGFloat delta = referenceWidth > 0 ? fabs(width - referenceWidth) : 0;
        if (delta < bestDelta) {
            bestDelta = delta;
            bestFont = font;
            bestWidth = width;
        }
        if (referenceWidth <= 0) { break; }
    }
    if (!bestFont) {
        bestFont = [UIFont systemFontOfSize:pointSize weight:UIFontWeightBold];
        bestWidth = [text sizeWithAttributes:@{NSFontAttributeName : bestFont}].width;
    }

    // Clamp the glyph size so the realised advance width matches the reference render
    // without letting a bad candidate change the type hierarchy.
    UIFont *resolved = bestFont;
    CGFloat scale = 1.0;
    if (referenceWidth > 0 && bestWidth > 0) {
        CGFloat proposed = referenceWidth / bestWidth;
        scale = MAX(0.80, MIN(1.20, proposed));
        if (fabs(scale - 1.0) <= 0.005) {
            scale = 1.0;
        } else {
            UIFont *scaled = [UIFont fontWithName:bestFont.fontName size:pointSize * scale];
            if (scaled) {
                resolved = scaled;
            } else {
                scale = 1.0;
            }
        }
    }

    NSLog(@"IHEREFOR_FONT_RESOLVED text=%@ cssPointSize=%.2f class=%ld referenceWidth=%.2f "
          @"chosenFace=%@ chosenWidth=%.2f glyphScale=%.4f finalPointSize=%.2f",
          text, pointSize, (long)weightClass, referenceWidth,
          bestFont.fontName, bestWidth, scale, resolved.pointSize);
    return resolved;
}

+ (void)logFontCandidatesForText:(NSString *)text
                       pointSize:(CGFloat)pointSize
                  referenceWidth:(CGFloat)referenceWidth {
    NSMutableArray<NSString *> *lines = [NSMutableArray array];
    for (NSString *face in StyleSelectionFontCandidates()) {
        UIFont *font = [UIFont fontWithName:face size:pointSize];
        if (!font) { continue; }
        CGFloat width = [text sizeWithAttributes:@{NSFontAttributeName : font}].width;
        [lines addObject:[NSString stringWithFormat:@"%@=%.2f(d=%.2f)", face, width,
                          fabs(width - referenceWidth)]];
    }
    NSLog(@"IHEREFOR_FONT_CANDIDATES text=%@ pointSize=%.2f referenceWidth=%.2f %@",
          text, pointSize, referenceWidth, [lines componentsJoinedByString:@" "]);
}

@end
