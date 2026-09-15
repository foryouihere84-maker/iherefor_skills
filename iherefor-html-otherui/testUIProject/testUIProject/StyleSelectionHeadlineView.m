//
//  StyleSelectionHeadlineView.m
//  testUIProject
//

#import "StyleSelectionHeadlineView.h"

/// index.css .text-wrapper_2 resolves to 328x62 at canvas (33, 108).
static const CGSize kHeadlineDesignSize = {328.0, 62.0};

/// The design renders the headline across two lines, both right-aligned. The reference
/// (page-facts textMetrics.rects) wraps the 42-char body as:
///     line 1: "What type of artwork do you"   (27 chars, 326.72pt device)   top ~ -2pt
///     line 2: "enjoy coloring" + "？"           (14 chars + ？, 185.93+24.55pt) top ~ 36pt
/// The break is at "you" / "enjoy" — confirmed from textMetrics.rects (first line
/// advanceWidth 326.72pt = 27 chars, second line 185.93pt = 14 chars) and the ink
/// projection of the reference. iOS Avenir-Black is metric-compatible with macOS
/// Chromium's Avenir Black (<0.2% width delta), so no glyph scaling is needed: the exact
/// break + right alignment reproduce the design. The body uses Avenir-Black, the ？ mark
/// uses PingFangSC-Semibold, both at the design 24pt.
static const CGFloat kQuestionTopDesign = -2.0;   // first line box tops out 2pt above the box
static const CGFloat kMarkTopDesign = 36.0;       // second line box (measured from the box top)

@interface StyleSelectionHeadlineView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@end

@implementation StyleSelectionHeadlineView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = NO;
        self.backgroundColor = UIColor.clearColor;

        // --- line 1: "What type of artwork do you" ---------------------------
        _questionLabel = [self makeLabelWithText:@"What type of artwork do you"
                                       styleName:@"headlineQuestion"
                                     weightClass:StyleSelectionFontWeightClassBlack];
        _questionLabel.accessibilityIdentifier = @"styleSelection.headline.question";
        [self addSubview:_questionLabel];
        [NSLayoutConstraint activateConstraints:[self trailingConstraintsForLabel:_questionLabel
                                                                        topDesign:kQuestionTopDesign]];

        // --- line 2: "enjoy coloring" + "？" -----------------------------------
        _markLabel = [self makeTwoFaceLabelWithBody:@"enjoy coloring"
                                          bodyClass:StyleSelectionFontWeightClassBlack
                                           markText:@"？"
                                          markClass:StyleSelectionFontWeightClassSystem];
        _markLabel.accessibilityIdentifier = @"styleSelection.headline.mark";
        [self addSubview:_markLabel];
        [NSLayoutConstraint activateConstraints:[self trailingConstraintsForLabel:_markLabel
                                                                        topDesign:kMarkTopDesign]];

        NSLog(@"IHEREFOR_REGION_FRAME name=StyleSelectionHeadlineView w=%.3f h=%.3f "
              @"questionTopDesign=%.3f markTopDesign=%.3f anchor=trailing(flush)",
              kHeadlineDesignSize.width, kHeadlineDesignSize.height,
              kQuestionTopDesign, kMarkTopDesign);
    }
    return self;
}

- (UILabel *)makeLabelWithText:(NSString *)text
                     styleName:(NSString *)styleName
                   weightClass:(StyleSelectionFontWeightClass)weightClass {
    UILabel *label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.translatesAutoresizingMaskIntoConstraints = NO;
    label.text = text;
    label.numberOfLines = 1;
    label.lineBreakMode = NSLineBreakByClipping;
    label.textAlignment = NSTextAlignmentRight;
    label.textColor = StyleSelectionStyle.headlineTextColor;
    label.font = [self fontForText:text class:weightClass styleName:styleName];
    return label;
}

/// Second line carries two faces: the body word in one font and the ？ mark in another,
/// concatenated so the whole line is one right-aligned run.
- (UILabel *)makeTwoFaceLabelWithBody:(NSString *)body
                            bodyClass:(StyleSelectionFontWeightClass)bodyClass
                             markText:(NSString *)markText
                            markClass:(StyleSelectionFontWeightClass)markClass {
    UILabel *label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.translatesAutoresizingMaskIntoConstraints = NO;
    label.numberOfLines = 1;
    label.lineBreakMode = NSLineBreakByClipping;
    label.textAlignment = NSTextAlignmentRight;
    label.textColor = StyleSelectionStyle.headlineTextColor;

    UIFont *bodyFont = [self fontForText:body class:bodyClass styleName:@"headlineMark"];
    UIFont *markFont = [self fontForText:markText class:markClass styleName:@"headlineMark"];

    NSMutableAttributedString *as = [[NSMutableAttributedString alloc] init];
    [as appendAttributedString:[[NSAttributedString alloc] initWithString:body
                                                               attributes:@{NSFontAttributeName: bodyFont}]];
    [as appendAttributedString:[[NSAttributedString alloc] initWithString:markText
                                                               attributes:@{NSFontAttributeName: markFont}]];
    label.attributedText = as;
    return label;
}

- (UIFont *)fontForText:(NSString *)text
                  class:(StyleSelectionFontWeightClass)weightClass
              styleName:(NSString *)styleName {
    return [StyleSelectionStyle fontForText:text
                                      class:weightClass
                                  pointSize:[StyleSelectionStyle pointSizeForStyleName:styleName]
                             referenceWidth:[StyleSelectionStyle referenceWidthForStyleName:styleName]];
}

/// Right-aligned with an intrinsic-width label: the label's trailing edge is flush with
/// the box's trailing edge. origin.x == box width makes closeChild emit a plain
/// trailing-to-trailing pin (no spacer, no ratio).
- (NSArray<NSLayoutConstraint *> *)trailingConstraintsForLabel:(UILabel *)label
                                                    topDesign:(CGFloat)topDesign {
    return [StyleSelectionStyle closeChild:label
                                    parent:self
                               designFrame:CGRectMake(kHeadlineDesignSize.width, topDesign, 0.0, 0.0)
                          parentDesignSize:kHeadlineDesignSize
                                  sizeMode:StyleSelectionClosureSizeIntrinsic
                                    anchor:StyleSelectionClosureAnchorTrailing];
}

@end
