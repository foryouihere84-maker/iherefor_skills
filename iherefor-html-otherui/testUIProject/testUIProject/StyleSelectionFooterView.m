//
//  StyleSelectionFooterView.m
//  testUIProject
//

#import "StyleSelectionFooterView.h"

/// index.css .group_10 resolves to 393x190.
static const CGSize kFooterDesignSize = {393.0, 190.0};
/// .text-wrapper_11: 341x56 pill, 26pt in from each side and 66pt below the scrim top.
/// 56pt tall keeps the control above the 44pt platform minimum hit target.
static const CGRect kContinueButtonDesignFrame = {{26.0, 66.0}, {341.0, 56.0}};
/// .text_13 sits at (124, 17) inside the pill.
static const CGRect kContinueLabelDesignFrame = {{124.0, 17.0}, {67.0, 22.0}};

@interface StyleSelectionFooterView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, strong) UIImageView *scrimImageView;
@property(nonatomic, strong) UIButton *continueButton;
@property(nonatomic, strong) UILabel *continueLabel;
@end

@implementation StyleSelectionFooterView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = NO;
        self.backgroundColor = UIColor.clearColor;

        // --- scrim -------------------------------------------------------------
        // img_14 is an alpha ramp over its first ~64pt (0 -> 255) followed by solid
        // page-colour, which is what makes the third option row fade out behind the CTA.
        _scrimImageView = [[UIImageView alloc] initWithFrame:CGRectZero];
        _scrimImageView.translatesAutoresizingMaskIntoConstraints = NO;
        _scrimImageView.contentMode = UIViewContentModeScaleToFill;
        _scrimImageView.clipsToBounds = YES;
        _scrimImageView.image = [self imageNamed:@"style_selection_bottom_scrim"];
        _scrimImageView.accessibilityIdentifier = @"styleSelection.bottomScrim";
        [self addSubview:_scrimImageView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_scrimImageView
                                                                       parent:self
                                                                  designFrame:CGRectMake(0.0, 0.0,
                                                                                         kFooterDesignSize.width,
                                                                                         kFooterDesignSize.height)
                                                             parentDesignSize:kFooterDesignSize]];

        // --- primary CTA -------------------------------------------------------
        _continueButton = [UIButton buttonWithType:UIButtonTypeCustom];
        _continueButton.translatesAutoresizingMaskIntoConstraints = NO;
        _continueButton.backgroundColor = UIColor.clearColor;
        _continueButton.accessibilityIdentifier = @"styleSelection.continue";
        _continueButton.layer.cornerRadius = [StyleSelectionStyle continueButtonCornerRadius];
        _continueButton.clipsToBounds = YES;
        [_continueButton setBackgroundImage:[self imageNamed:@"style_selection_continue_button_background"]
                                   forState:UIControlStateNormal];
        [self addSubview:_continueButton];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_continueButton
                                                                       parent:self
                                                                  designFrame:kContinueButtonDesignFrame
                                                             parentDesignSize:kFooterDesignSize]];

        // The title is a real label subview rather than the button's own titleLabel:
        // positioning it with constraints reproduces the design offset (.text_13 sits
        // 124pt in at the canvas scale) exactly, and it keeps the text measurable and
        // accessible. On iOS 15+ -contentEdgeInsets is deprecated and ignored, so it is
        // deliberately not used here.
        _continueLabel = [[UILabel alloc] initWithFrame:CGRectZero];
        _continueLabel.translatesAutoresizingMaskIntoConstraints = NO;
        _continueLabel.text = @"Continue";
        _continueLabel.numberOfLines = 1;
        _continueLabel.lineBreakMode = NSLineBreakByClipping;
        _continueLabel.textAlignment = NSTextAlignmentLeft;
        _continueLabel.textColor = StyleSelectionStyle.cardLabelTextColor;
        _continueLabel.font = [StyleSelectionStyle fontForText:_continueLabel.text
                                                         class:StyleSelectionFontWeightClassMedium
                                                     pointSize:[StyleSelectionStyle pointSizeForStyleName:@"continueTitle"]
                                                referenceWidth:[StyleSelectionStyle referenceWidthForStyleName:@"continueTitle"]];
        _continueLabel.userInteractionEnabled = NO;
        _continueLabel.accessibilityIdentifier = @"styleSelection.continue.label";
        [_continueButton addSubview:_continueLabel];
        // Leading/top only: the advance width and line height are font properties, so
        // the box is never closed onto a container ratio. Offsets go through the shared
        // closure, which expresses them as spacer guides -- a bare
        // `label.leading = button.width x ratio` is an illegal position-to-size pairing
        // and throws at constraint-creation time.
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_continueLabel
                                                                        parent:_continueButton
                                                                   designFrame:CGRectMake(kContinueLabelDesignFrame.origin.x,
                                                                                          kContinueLabelDesignFrame.origin.y,
                                                                                          0.0, 0.0)
                                                              parentDesignSize:kContinueButtonDesignFrame.size
                                                                      sizeMode:StyleSelectionClosureSizeIntrinsic
                                                                        anchor:StyleSelectionClosureAnchorLeading]];

        NSLog(@"IHEREFOR_REGION_FRAME name=StyleSelectionFooterView designW=%.0f designH=%.0f "
              @"continueBtn=(%.0f,%.0f,%.0f,%.0f) cornerRadius=%.1f labelLeadingDesign=%.1f labelTopDesign=%.1f",
              kFooterDesignSize.width, kFooterDesignSize.height,
              kContinueButtonDesignFrame.origin.x, kContinueButtonDesignFrame.origin.y,
              kContinueButtonDesignFrame.size.width, kContinueButtonDesignFrame.size.height,
              [StyleSelectionStyle continueButtonCornerRadius],
              kContinueLabelDesignFrame.origin.x, kContinueLabelDesignFrame.origin.y);
        NSLog(@"IHEREFOR_IMAGE_FRAME name=style_selection_bottom_scrim role=bottomScrim designW=%.0f designH=%.0f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
              kFooterDesignSize.width, kFooterDesignSize.height,
              _scrimImageView.image.size.width, _scrimImageView.image.size.height);
        NSLog(@"IHEREFOR_IMAGE_FRAME name=style_selection_continue_button_background role=ctaPill designW=%.0f designH=%.0f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
              kContinueButtonDesignFrame.size.width, kContinueButtonDesignFrame.size.height,
              [_continueButton backgroundImageForState:UIControlStateNormal].size.width,
              [_continueButton backgroundImageForState:UIControlStateNormal].size.height);
    }
    return self;
}

- (UIImage *)imageNamed:(NSString *)name {
    UIImage *image = [UIImage imageNamed:name];
    if (!image) {
        NSString *path = [[NSBundle mainBundle] pathForResource:name ofType:@"png"];
        if (path.length) {
            image = [UIImage imageWithContentsOfFile:path];
        }
    }
    return image;
}

@end
