//
//  AgeOptionCardView.m
//  testUIProject
//

#import "AgeOptionCardView.h"
#import "AgeSelectionStyle.h"

/// Design constants from index.css (`.box_4` / `.box_5` / `.block_*`).
/// Inner padding-left 15.5pt, emoji glyph width 21pt, no gap to the label; the
/// card itself is sized by its parent constraints (353 x 65), not here.
static const CGFloat kAgeCardBorderWidth = 1.5;
static const CGFloat kAgeCardCornerRadius = 12.0;
static const CGFloat kAgeCardInnerLeading = 16.5;   ///< border(1.5) + padding-left(15.5): emoji leading inset
static const CGFloat kAgeCardEmojiWidth = 21.0;     ///< emoji glyph advance
static const CGFloat kAgeCardInnerTop = 21.5;       ///< content top = padding-top(20.5) + ~1 (border box)

@interface AgeOptionCardView ()
@property(nonatomic, strong) UILabel *emojiLabel;
@property(nonatomic, strong) UILabel *textLabel;
@end

@implementation AgeOptionCardView

- (instancetype)initWithEmoji:(NSString *)emoji label:(NSString *)label {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _emoji = [emoji copy];
        _optionLabel = [label copy];
        [self commonInit];
    }
    return self;
}

- (instancetype)initWithCoder:(NSCoder *)coder {
    self = [super initWithCoder:coder];
    if (self) {
        [self commonInit];
    }
    return self;
}

- (void)commonInit {
    self.backgroundColor = AgeSelectionStyle.cardBackgroundColor;
    self.layer.cornerRadius = kAgeCardCornerRadius;
    self.layer.borderWidth = kAgeCardBorderWidth;
    self.layer.masksToBounds = YES;
    self.selectedState = NO;

    _emojiLabel = [[UILabel alloc] init];
    _emojiLabel.translatesAutoresizingMaskIntoConstraints = NO;
    _emojiLabel.text = self.emoji;
    _emojiLabel.font = AgeSelectionStyle.emojiFont;
    _emojiLabel.textColor = AgeSelectionStyle.primaryTextColor;
    _emojiLabel.textAlignment = NSTextAlignmentLeft;
    [self addSubview:_emojiLabel];

    _textLabel = [[UILabel alloc] init];
    _textLabel.translatesAutoresizingMaskIntoConstraints = NO;
    _textLabel.text = self.optionLabel;
    _textLabel.font = AgeSelectionStyle.optionFont;
    _textLabel.textColor = AgeSelectionStyle.primaryTextColor;
    _textLabel.textAlignment = NSTextAlignmentLeft;
    _textLabel.lineBreakMode = NSLineBreakByClipping;
    [self addSubview:_textLabel];

    [NSLayoutConstraint activateConstraints:@[
        [_emojiLabel.leadingAnchor constraintEqualToAnchor:self.leadingAnchor
                                                 constant:kAgeCardInnerLeading],
        [_emojiLabel.topAnchor constraintEqualToAnchor:self.topAnchor
                                             constant:kAgeCardInnerTop],
        [_emojiLabel.widthAnchor constraintEqualToConstant:kAgeCardEmojiWidth],
        [_textLabel.leadingAnchor constraintEqualToAnchor:_emojiLabel.trailingAnchor],
        [_textLabel.topAnchor constraintEqualToAnchor:self.topAnchor
                                            constant:kAgeCardInnerTop],
        [_textLabel.trailingAnchor constraintLessThanOrEqualToAnchor:self.trailingAnchor
                                                            constant:-kAgeCardInnerLeading],
    ]];

    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleTap:)];
    [self addGestureRecognizer:tap];
}

#pragma mark - State

- (void)setSelectedState:(BOOL)selectedState {
    _selectedState = selectedState;
    self.layer.borderColor = selectedState
        ? AgeSelectionStyle.cardSelectedBorderColor.CGColor
        : AgeSelectionStyle.cardBorderColor.CGColor;
}

#pragma mark - Actions

- (void)handleTap:(UITapGestureRecognizer *)recognizer {
    if (self.onTap) {
        self.onTap(self);
    }
}

@end
