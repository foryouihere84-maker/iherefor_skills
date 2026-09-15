//
//  StyleSelectionNavRowView.m
//  testUIProject
//

#import "StyleSelectionNavRowView.h"

/// index.css .section_6 resolves to 361x32 at canvas y=52.
static const CGSize kNavRowDesignSize = {361.0, 32.0};
/// .label_1 is a 32x32 box whose visible pixels are only 17x12 (alpha bias 8,10,25,22),
/// so the artwork must be drawn at its natural size, centred, never stretched.
static const CGRect kBackIconDesignFrame = {{0.0, 0.0}, {32.0, 32.0}};
/// 44pt is the platform minimum hit target. The control is grown around the 32pt icon
/// instead of shrinking the icon, so the drawing keeps the design frame.
static const CGRect kBackButtonDesignFrame = {{-6.0, -6.0}, {44.0, 44.0}};
/// The 44pt Skip hit target is grown around the 26.97x24 "Skip" text box (row-relative
/// 334,8), in the same way the back control grows around its icon: 6pt out each side,
/// and vertically so the 44pt height straddles the row centre (the row is only 32pt high).
static const CGRect kSkipButtonDesignFrame = {{328.0, -6.0}, {33.0, 44.0}};
/// .group_3: 232x6 track, 13pt below the row top and 69pt from its leading edge.
static const CGRect kProgressTrackDesignFrame = {{69.0, 13.0}, {232.0, 6.0}};
/// .text_3 ("Skip") sits at row-relative (334, 8) with a 24pt line box.
static const CGRect kSkipLabelDesignFrame = {{334.0, 8.0}, {26.97, 24.0}};

@interface StyleSelectionNavRowView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, strong) UIImageView *backIconView;
@property(nonatomic, strong) NSLayoutConstraint *progressFillWidthConstraint;
@end

@implementation StyleSelectionNavRowView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = NO;
        self.backgroundColor = UIColor.clearColor;

        // --- back control ------------------------------------------------------
        _backButton = [UIButton buttonWithType:UIButtonTypeCustom];
        _backButton.translatesAutoresizingMaskIntoConstraints = NO;
        _backButton.backgroundColor = UIColor.clearColor;
        _backButton.accessibilityIdentifier = @"styleSelection.nav.back";
        _backButton.accessibilityLabel = @"Back";
        [self addSubview:_backButton];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_backButton
                                                                        parent:self
                                                                   designFrame:kBackButtonDesignFrame
                                                              parentDesignSize:kNavRowDesignSize]];

        UIImage *chevron = [self imageNamed:@"style_selection_back_chevron"];
        _backIconView = [[UIImageView alloc] initWithFrame:CGRectZero];
        _backIconView.translatesAutoresizingMaskIntoConstraints = NO;
        // The glyph occupies 17x12 inside a 32x32 transparent box: any mode that
        // rescales the image would distort the stroke weight.
        _backIconView.contentMode = UIViewContentModeCenter;
        _backIconView.image = chevron;
        _backIconView.userInteractionEnabled = NO;
        [_backButton addSubview:_backIconView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_backIconView
                                                                        parent:_backButton
                                                                   designFrame:kBackIconDesignFrame
                                                              parentDesignSize:kBackButtonDesignFrame.size]];

        // --- progress ----------------------------------------------------------
        _progressTrackView = [[UIView alloc] initWithFrame:CGRectZero];
        _progressTrackView.translatesAutoresizingMaskIntoConstraints = NO;
        _progressTrackView.backgroundColor = StyleSelectionStyle.progressTrackColor;
        _progressTrackView.layer.cornerRadius = [StyleSelectionStyle progressCornerRadius];
        _progressTrackView.clipsToBounds = YES;
        _progressTrackView.accessibilityIdentifier = @"styleSelection.progress.track";
        [self addSubview:_progressTrackView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_progressTrackView
                                                                        parent:self
                                                                   designFrame:kProgressTrackDesignFrame
                                                              parentDesignSize:kNavRowDesignSize]];

        _progressFillView = [[UIView alloc] initWithFrame:CGRectZero];
        _progressFillView.translatesAutoresizingMaskIntoConstraints = NO;
        _progressFillView.backgroundColor = StyleSelectionStyle.progressFillColor;
        _progressFillView.layer.cornerRadius = [StyleSelectionStyle progressCornerRadius];
        _progressFillView.accessibilityIdentifier = @"styleSelection.progress.fill";
        [_progressTrackView addSubview:_progressFillView];
        _progressFillWidthConstraint =
            [NSLayoutConstraint constraintWithItem:_progressFillView
                                        attribute:NSLayoutAttributeWidth
                                        relatedBy:NSLayoutRelationEqual
                                           toItem:_progressTrackView
                                        attribute:NSLayoutAttributeWidth
                                       multiplier:24.0 / kProgressTrackDesignFrame.size.width
                                         constant:0.0];
        [NSLayoutConstraint activateConstraints:@[
            [NSLayoutConstraint constraintWithItem:_progressFillView
                                        attribute:NSLayoutAttributeLeading
                                        relatedBy:NSLayoutRelationEqual
                                           toItem:_progressTrackView
                                        attribute:NSLayoutAttributeLeading
                                       multiplier:1.0
                                         constant:0.0],
            [NSLayoutConstraint constraintWithItem:_progressFillView
                                        attribute:NSLayoutAttributeTop
                                        relatedBy:NSLayoutRelationEqual
                                           toItem:_progressTrackView
                                        attribute:NSLayoutAttributeTop
                                       multiplier:1.0
                                         constant:0.0],
            [NSLayoutConstraint constraintWithItem:_progressFillView
                                        attribute:NSLayoutAttributeHeight
                                        relatedBy:NSLayoutRelationEqual
                                           toItem:_progressTrackView
                                        attribute:NSLayoutAttributeHeight
                                       multiplier:1.0
                                         constant:0.0],
            _progressFillWidthConstraint,
        ]];

        // --- Skip --------------------------------------------------------------
        // The button is a transparent hit target around a real UILabel, mirroring the
        // footer CTA: a button's own titleLabel is vertically stretched by the button's
        // 34pt intrinsic height, so the text is drawn as a separate label and the button
        // only supplies the tappable area.
        _skipButton = [UIButton buttonWithType:UIButtonTypeCustom];
        _skipButton.translatesAutoresizingMaskIntoConstraints = NO;
        _skipButton.backgroundColor = UIColor.clearColor;
        _skipButton.accessibilityIdentifier = @"styleSelection.nav.skip";
        _skipButton.accessibilityLabel = @"Skip";
        [self addSubview:_skipButton];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_skipButton
                                                                        parent:self
                                                                   designFrame:kSkipButtonDesignFrame
                                                              parentDesignSize:kNavRowDesignSize]];

        UILabel *skipLabel = [[UILabel alloc] initWithFrame:CGRectZero];
        skipLabel.translatesAutoresizingMaskIntoConstraints = NO;
        skipLabel.text = @"Skip";
        skipLabel.numberOfLines = 1;
        skipLabel.lineBreakMode = NSLineBreakByClipping;
        skipLabel.textAlignment = NSTextAlignmentLeft;
        skipLabel.textColor = StyleSelectionStyle.skipTextColor;
        skipLabel.font = [StyleSelectionStyle fontForText:@"Skip"
                                                     class:StyleSelectionFontWeightClassMedium
                                                 pointSize:[StyleSelectionStyle pointSizeForStyleName:@"skipTitle"]
                                            referenceWidth:[StyleSelectionStyle referenceWidthForStyleName:@"skipTitle"]];
        skipLabel.userInteractionEnabled = NO;
        skipLabel.accessibilityIdentifier = @"styleSelection.nav.skip.label";
        [self addSubview:skipLabel];
        // Leading/top only: the advance width and line height are font properties, so
        // the box is never closed onto a container ratio.
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:skipLabel
                                                                        parent:self
                                                                   designFrame:CGRectMake(kSkipLabelDesignFrame.origin.x,
                                                                                          kSkipLabelDesignFrame.origin.y,
                                                                                          0.0, 0.0)
                                                              parentDesignSize:kNavRowDesignSize
                                                                      sizeMode:StyleSelectionClosureSizeIntrinsic
                                                                        anchor:StyleSelectionClosureAnchorLeading]];

        NSLog(@"IHEREFOR_REGION_FRAME name=StyleSelectionNavRowView x=%.3f y=%.3f w=%.3f h=%.3f "
              @"backHitW=%.1f backHitH=%.1f chevronNaturalW=%.0f chevronNaturalH=%.0f contentMode=center",
              kNavRowDesignSize.width, kNavRowDesignSize.height, kNavRowDesignSize.width,
              kNavRowDesignSize.height, kBackButtonDesignFrame.size.width,
              kBackButtonDesignFrame.size.height, chevron.size.width, chevron.size.height);
        NSLog(@"IHEREFOR_IMAGE_FRAME name=style_selection_back_chevron role=backChevron designW=%.0f designH=%.0f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeCenter",
              kBackIconDesignFrame.size.width, kBackIconDesignFrame.size.height,
              chevron.size.width, chevron.size.height);
    }
    return self;
}

- (void)setProgressFillDesignWidth:(CGFloat)designWidth {
    CGFloat trackWidth = kProgressTrackDesignFrame.size.width;
    CGFloat ratio = trackWidth > 0 ? MAX(0.0, MIN(1.0, designWidth / trackWidth)) : 0.0;
    self.progressFillWidthConstraint.active = NO;
    self.progressFillWidthConstraint =
        [NSLayoutConstraint constraintWithItem:self.progressFillView
                                    attribute:NSLayoutAttributeWidth
                                    relatedBy:NSLayoutRelationEqual
                                       toItem:self.progressTrackView
                                    attribute:NSLayoutAttributeWidth
                                   multiplier:ratio
                                     constant:0.0];
    self.progressFillWidthConstraint.active = YES;
    NSLog(@"IHEREFOR_PROGRESS designFillWidth=%.3f trackDesignWidth=%.3f multiplier=%.6f",
          designWidth, trackWidth, ratio);
}

#pragma mark - Helpers

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
