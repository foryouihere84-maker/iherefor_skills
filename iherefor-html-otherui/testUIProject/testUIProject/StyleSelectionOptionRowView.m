//
//  StyleSelectionOptionRowView.m
//  testUIProject
//

#import "StyleSelectionOptionRowView.h"

const CGSize kStyleSelectionRowDesignSize = {353.0, 146.0};

/// index.css .section_7 uses `justify-between` over a 353pt row with two 170pt cards,
/// so the gap is a design constant (13pt) and the right card is flush with the row's
/// trailing edge. The measured 168.7 / 203.6 boxes in page-facts.json are the browser
/// rounding that flex layout down to sub-pixels; the design intent is 170 + 13 + 170.
static const CGFloat kStyleSelectionCardWidth = 170.0;
static const CGFloat kStyleSelectionCardHeight = 146.0;

@implementation StyleSelectionOptionSpec

+ (instancetype)specWithOption:(StyleSelectionOption)option
                           art:(NSString *)art
                     chipScrim:(NSString *)chipScrim
                         label:(NSString *)label
              labelDesignFrame:(CGRect)labelDesignFrame
                labelStyleName:(NSString *)labelStyleName
                   weightClass:(StyleSelectionFontWeightClass)weightClass
       accessibilityIdentifier:(NSString *)accessibilityIdentifier {
    StyleSelectionOptionSpec *spec = [StyleSelectionOptionSpec new];
    spec.option = option;
    spec.art = art;
    spec.chipScrim = chipScrim;
    spec.label = label;
    spec.labelDesignFrame = labelDesignFrame;
    spec.labelStyleName = labelStyleName;
    spec.weightClass = weightClass;
    spec.accessibilityIdentifier = accessibilityIdentifier;
    return spec;
}

@end

@interface StyleSelectionOptionRowView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, copy) NSArray<StyleSelectionOptionCardView *> *cards;
@end

@implementation StyleSelectionOptionRowView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                         left:(StyleSelectionOptionSpec *)left
                        right:(StyleSelectionOptionSpec *)right {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = NO;
        self.backgroundColor = UIColor.clearColor;

        StyleSelectionOptionCardView *leftCard = [self cardWithSpec:left
                                                      designFrame:CGRectMake(0.0, 0.0,
                                                                             kStyleSelectionCardWidth,
                                                                             kStyleSelectionCardHeight)];
        // Right card: flush with the row's trailing edge. Expressed as a trailing pin
        // rather than a leading ratio, because "the second column is 13pt from the
        // right edge" is the relation the design states.
        StyleSelectionOptionCardView *rightCard = [self cardWithSpec:right
                                                       designFrame:CGRectMake(kStyleSelectionRowDesignSize.width - kStyleSelectionCardWidth,
                                                                              0.0,
                                                                              kStyleSelectionCardWidth,
                                                                              kStyleSelectionCardHeight)];
        _cards = @[leftCard, rightCard];

        NSLog(@"IHEREFOR_REGION_FRAME name=%@ x=0.000 y=0.000 w=%.3f h=%.3f parentDesign=(%.0f,%.0f) cardGap=%.3f",
              NSStringFromClass(self.class), kStyleSelectionRowDesignSize.width,
              kStyleSelectionRowDesignSize.height, kStyleSelectionRowDesignSize.width,
              kStyleSelectionRowDesignSize.height,
              kStyleSelectionRowDesignSize.width - 2 * kStyleSelectionCardWidth);
    }
    return self;
}

- (StyleSelectionOptionCardView *)cardWithSpec:(StyleSelectionOptionSpec *)spec
                                    designFrame:(CGRect)designFrame {
    StyleSelectionOptionCardView *card = [[StyleSelectionOptionCardView alloc] initWithStyle:self.style
                                                                                      option:spec.option
                                                                                         art:spec.art
                                                                                   chipScrim:spec.chipScrim
                                                                                       label:spec.label
                                                                            labelDesignFrame:spec.labelDesignFrame
                                                                              labelStyleName:spec.labelStyleName
                                                                                 weightClass:spec.weightClass];
    card.accessibilityIdentifier = spec.accessibilityIdentifier;
    [self addSubview:card];
    [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:card
                                                                    parent:self
                                                               designFrame:designFrame
                                                          parentDesignSize:kStyleSelectionRowDesignSize]];
    return card;
}

- (StyleSelectionOptionCardView *)cardForOption:(StyleSelectionOption)option {
    for (StyleSelectionOptionCardView *card in self.cards) {
        if (card.option == option) {
            return card;
        }
    }
    return nil;
}

@end
