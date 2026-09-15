//
//  PaletteCardView.m
//  testUIProject
//

#import "PaletteCardView.h"
#import "PaletteSelectionStyle.h"

static const CGFloat kCardCornerRadius = 12.0;
static const CGFloat kCardBorderWidth = 1.5;
static const CGFloat kSwatchWidth = 152.0;
static const CGFloat kSwatchHeight = 55.0;
static const CGFloat kTitleHeight = 19.0;
static const CGFloat kTitleTop = 4.5;
static const CGFloat kSwatchTop = 31.5; // 4.5 (title top) + 19 (title) + 8 (margin)

@interface PaletteCardView ()
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UIImageView *swatchImageView;
@end

@implementation PaletteCardView

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.backgroundColor = PaletteSelectionStyle.cardBackgroundColor;
        self.layer.cornerRadius = kCardCornerRadius;
        self.layer.borderWidth = kCardBorderWidth;
        self.layer.masksToBounds = YES;
        [self updateBorder];

        _titleLabel = [[UILabel alloc] init];
        _titleLabel.font = PaletteSelectionStyle.cardTitleFont;
        _titleLabel.textColor = PaletteSelectionStyle.cardTitleTextColor;
        _titleLabel.textAlignment = NSTextAlignmentCenter;
        _titleLabel.translatesAutoresizingMaskIntoConstraints = NO;
        [self addSubview:_titleLabel];

        _swatchImageView = [[UIImageView alloc] init];
        _swatchImageView.contentMode = UIViewContentModeScaleToFill;
        _swatchImageView.translatesAutoresizingMaskIntoConstraints = NO;
        [self addSubview:_swatchImageView];

        [NSLayoutConstraint activateConstraints:@[
            [_titleLabel.topAnchor constraintEqualToAnchor:self.topAnchor constant:kTitleTop],
            [_titleLabel.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
            [_titleLabel.heightAnchor constraintEqualToConstant:kTitleHeight],

            [_swatchImageView.topAnchor constraintEqualToAnchor:self.topAnchor constant:kSwatchTop],
            [_swatchImageView.centerXAnchor constraintEqualToAnchor:self.centerXAnchor],
            [_swatchImageView.widthAnchor constraintEqualToConstant:kSwatchWidth],
            [_swatchImageView.heightAnchor constraintEqualToConstant:kSwatchHeight],
        ]];
    }
    return self;
}

- (void)setTitle:(NSString *)title {
    _title = [title copy];
    self.titleLabel.text = title;
}

- (void)setSwatchImageName:(NSString *)swatchImageName {
    _swatchImageName = [swatchImageName copy];
    self.swatchImageView.image = [UIImage imageNamed:swatchImageName];
}

- (void)setSelected:(BOOL)selected {
    _selected = selected;
    [self updateBorder];
}

- (void)updateBorder {
    self.layer.borderColor = self.selected
        ? PaletteSelectionStyle.selectedBorderColor.CGColor
        : PaletteSelectionStyle.cardBorderColor.CGColor;
}

@end
