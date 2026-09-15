//
//  StyleSelectionHeroView.m
//  testUIProject
//

#import "StyleSelectionHeroView.h"

/// index.css .box_1 resolves to 393x365 at canvas (0, 0).
static const CGSize kHeroDesignSize = {393.0, 365.0};
/// .section_6 sits at (12, 52); .section_7 at (20, 206); .text-wrapper_2 at (33, 108).
static const CGRect kNavRowDesignFrame = {{12.0, 52.0}, {361.0, 32.0}};
static const CGRect kHeadlineDesignFrame = {{33.0, 108.0}, {328.0, 62.0}};
static const CGRect kTopOptionRowDesignFrame = {{20.0, 206.0}, {353.0, 146.0}};

@interface StyleSelectionHeroView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, strong) UIImageView *washImageView;
@property(nonatomic, strong) StyleSelectionNavRowView *navRowView;
@property(nonatomic, strong) StyleSelectionHeadlineView *headlineView;
@property(nonatomic, strong) StyleSelectionOptionRowView *optionRowView;
@end

@implementation StyleSelectionHeroView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
             topOptionRowView:(StyleSelectionOptionRowView *)optionRowView {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = YES;
        self.backgroundColor = StyleSelectionStyle.pageBackgroundColor;

        // --- soft wash ---------------------------------------------------------
        // img_4 is a flat wash: every pixel carries alpha 129, so it must be composited
        // over the page background rather than made opaque. 393x365 fills the region
        // exactly, hence a full-bleed closure onto the parent.
        _washImageView = [[UIImageView alloc] initWithFrame:CGRectZero];
        _washImageView.translatesAutoresizingMaskIntoConstraints = NO;
        _washImageView.contentMode = UIViewContentModeScaleToFill;
        _washImageView.clipsToBounds = YES;
        _washImageView.image = [self imageNamed:@"style_selection_hero_wash"];
        _washImageView.accessibilityIdentifier = @"styleSelection.hero.wash";
        [self addSubview:_washImageView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_washImageView
                                                                       parent:self
                                                                  designFrame:CGRectMake(0.0, 0.0,
                                                                                         kHeroDesignSize.width,
                                                                                         kHeroDesignSize.height)
                                                             parentDesignSize:kHeroDesignSize]];

        // --- navigation row ----------------------------------------------------
        _navRowView = [[StyleSelectionNavRowView alloc] initWithStyle:style];
        [self addSubview:_navRowView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_navRowView
                                                                       parent:self
                                                                  designFrame:kNavRowDesignFrame
                                                             parentDesignSize:kHeroDesignSize]];

        // --- headline ----------------------------------------------------------
        _headlineView = [[StyleSelectionHeadlineView alloc] initWithStyle:style];
        _headlineView.accessibilityIdentifier = @"styleSelection.headline";
        [self addSubview:_headlineView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_headlineView
                                                                       parent:self
                                                                  designFrame:kHeadlineDesignFrame
                                                             parentDesignSize:kHeroDesignSize]];

        // --- first option row --------------------------------------------------
        _optionRowView = optionRowView;
        _optionRowView.accessibilityIdentifier = @"styleSelection.row.top";
        [self addSubview:_optionRowView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_optionRowView
                                                                       parent:self
                                                                  designFrame:kTopOptionRowDesignFrame
                                                             parentDesignSize:kHeroDesignSize]];

        NSLog(@"IHEREFOR_REGION_FRAME name=StyleSelectionHeroView designW=%.0f designH=%.0f "
              @"navRow=(%.0f,%.0f,%.0f,%.0f) headline=(%.0f,%.0f,%.0f,%.0f) topRow=(%.0f,%.0f,%.0f,%.0f) clipsToBounds=YES",
              kHeroDesignSize.width, kHeroDesignSize.height,
              kNavRowDesignFrame.origin.x, kNavRowDesignFrame.origin.y,
              kNavRowDesignFrame.size.width, kNavRowDesignFrame.size.height,
              kHeadlineDesignFrame.origin.x, kHeadlineDesignFrame.origin.y,
              kHeadlineDesignFrame.size.width, kHeadlineDesignFrame.size.height,
              kTopOptionRowDesignFrame.origin.x, kTopOptionRowDesignFrame.origin.y,
              kTopOptionRowDesignFrame.size.width, kTopOptionRowDesignFrame.size.height);
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
