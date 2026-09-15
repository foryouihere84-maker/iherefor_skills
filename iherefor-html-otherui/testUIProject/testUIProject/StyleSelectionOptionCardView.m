//
//  StyleSelectionOptionCardView.m
//  testUIProject
//

#import "StyleSelectionOptionCardView.h"

const CGSize kStyleSelectionCardDesignSize = {170.0, 146.0};
const CGRect kStyleSelectionChipScrimDesignFrame = {{0.0, 78.0}, {170.0, 68.0}};
// index.css .box_3 is `left:0; top:0; width:173px; height:149px; border:1.5px`, and
// common.css sets `box-sizing: border-box`, so the 173x149 IS the border box and the
// stroke is painted inside it. A UIView of the same size with layer.borderWidth = 1.5
// draws its stroke inside its bounds too, so this reproduces the reference exactly --
// and, unlike a -1.5 origin, it needs no negative (unsatisfiable) width constraint.
const CGRect kStyleSelectionSelectionRingDesignFrame = {{0.0, 0.0}, {173.0, 149.0}};

@interface StyleSelectionOptionCardView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, strong) UIImageView *artImageView;
@property(nonatomic, strong) UIImageView *chipScrimView;
@property(nonatomic, strong) UILabel *label;
@property(nonatomic, strong) UIView *selectionRingView;
@end

@implementation StyleSelectionOptionCardView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                       option:(StyleSelectionOption)option
                          art:(NSString *)artImageName
                    chipScrim:(NSString *)chipScrimImageName
                        label:(NSString *)label
             labelDesignFrame:(CGRect)labelDesignFrame
               labelStyleName:(NSString *)labelStyleName
                  weightClass:(StyleSelectionFontWeightClass)weightClass {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        _option = option;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        // The selection ring is larger than the card, so nothing may be clipped.
        self.clipsToBounds = NO;
        self.backgroundColor = UIColor.clearColor;

        // --- artwork: fills the whole card -------------------------------------
        _artImageView = [[UIImageView alloc] initWithFrame:CGRectZero];
        _artImageView.translatesAutoresizingMaskIntoConstraints = NO;
        _artImageView.contentMode = UIViewContentModeScaleToFill;
        _artImageView.clipsToBounds = YES;
        _artImageView.image = [self imageNamed:artImageName];
        _artImageView.accessibilityIdentifier = @"styleSelection.card.art";
        [self addSubview:_artImageView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_artImageView
                                                                       parent:self
                                                                  designFrame:CGRectMake(0.0, 0.0,
                                                                                         kStyleSelectionCardDesignSize.width,
                                                                                         kStyleSelectionCardDesignSize.height)
                                                             parentDesignSize:kStyleSelectionCardDesignSize]];

        // --- optional chip scrim ----------------------------------------------
        // img_6 is a black-to-transparent wipe (alpha 0 -> 229 downwards) that darkens
        // the bottom of the artwork so the white label stays legible. The three
        // right-hand cards in the lower grid ship their scrim already composited into
        // the artwork, which is why they pass nil here.
        UIView *labelParent = self;
        CGSize labelParentDesignSize = kStyleSelectionCardDesignSize;
        if (chipScrimImageName.length) {
            _chipScrimView = [[UIImageView alloc] initWithFrame:CGRectZero];
            _chipScrimView.translatesAutoresizingMaskIntoConstraints = NO;
            _chipScrimView.contentMode = UIViewContentModeScaleToFill;
            _chipScrimView.clipsToBounds = YES;
            _chipScrimView.image = [self imageNamed:chipScrimImageName];
            _chipScrimView.accessibilityIdentifier = @"styleSelection.card.chipScrim";
            [self addSubview:_chipScrimView];
            [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_chipScrimView
                                                                           parent:self
                                                                      designFrame:kStyleSelectionChipScrimDesignFrame
                                                                 parentDesignSize:kStyleSelectionCardDesignSize]];
            labelParent = _chipScrimView;
            labelParentDesignSize = kStyleSelectionChipScrimDesignFrame.size;
        }

        // --- label -------------------------------------------------------------
        _label = [[UILabel alloc] initWithFrame:CGRectZero];
        _label.translatesAutoresizingMaskIntoConstraints = NO;
        _label.text = label;
        _label.numberOfLines = 1;
        _label.lineBreakMode = NSLineBreakByClipping;
        _label.textAlignment = NSTextAlignmentLeft;
        _label.textColor = StyleSelectionStyle.cardLabelTextColor;
        _label.font = [StyleSelectionStyle fontForText:label
                                                  class:weightClass
                                              pointSize:[StyleSelectionStyle pointSizeForStyleName:labelStyleName]
                                         referenceWidth:[StyleSelectionStyle referenceWidthForStyleName:labelStyleName]];
        _label.accessibilityIdentifier = @"styleSelection.card.label";
        [labelParent addSubview:_label];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_label
                                                                       parent:labelParent
                                                                  designFrame:labelDesignFrame
                                                             parentDesignSize:labelParentDesignSize]];

        // --- selection ring (added last so it draws on top) --------------------
        _selectionRingView = [[UIView alloc] initWithFrame:CGRectZero];
        _selectionRingView.translatesAutoresizingMaskIntoConstraints = NO;
        _selectionRingView.backgroundColor = UIColor.clearColor;
        _selectionRingView.layer.borderWidth = [StyleSelectionStyle selectionRingBorderWidth];
        _selectionRingView.layer.borderColor = StyleSelectionStyle.selectionRingColor.CGColor;
        _selectionRingView.layer.cornerRadius = [StyleSelectionStyle selectionRingCornerRadius];
        _selectionRingView.hidden = YES;
        _selectionRingView.userInteractionEnabled = NO;
        _selectionRingView.accessibilityIdentifier = @"styleSelection.card.selectionRing";
        [self addSubview:_selectionRingView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_selectionRingView
                                                                       parent:self
                                                                  designFrame:kStyleSelectionSelectionRingDesignFrame
                                                             parentDesignSize:kStyleSelectionCardDesignSize]];

        NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ role=cardArt designW=%.0f designH=%.0f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
              artImageName, kStyleSelectionCardDesignSize.width, kStyleSelectionCardDesignSize.height,
              _artImageView.image.size.width, _artImageView.image.size.height);
        if (_chipScrimView) {
            NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ role=chipScrim designW=%.0f designH=%.0f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
                  chipScrimImageName, kStyleSelectionChipScrimDesignFrame.size.width,
                  kStyleSelectionChipScrimDesignFrame.size.height,
                  _chipScrimView.image.size.width, _chipScrimView.image.size.height);
        }
    }
    return self;
}

- (void)setRingVisible:(BOOL)ringVisible {
    _ringVisible = ringVisible;
    self.selectionRingView.hidden = !ringVisible;
    self.selected = ringVisible;
}

- (void)setSelected:(BOOL)selected {
    [super setSelected:selected];
    self.alpha = selected ? 1.0 : 1.0;
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
