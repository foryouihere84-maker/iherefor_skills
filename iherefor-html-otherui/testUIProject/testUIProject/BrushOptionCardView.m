//
//  BrushOptionCardView.m
//  testUIProject
//

#import "BrushOptionCardView.h"
#import "BrushSelectionStyle.h"

/// Design constants, all read straight out of index.css. None of them scale with
/// the screen: the canvas is a fit-mapped design board, so these stay at their
/// design values exactly like the font sizes do.
static const CGFloat kBrushCardCornerRadius = 12.0;      ///< `.list-items_* { border-radius: 12px }`
static const CGFloat kBrushCardRingWidth = 2.5;          ///< collapsed double stroke (see header)
static const CGFloat kBrushCardBorderInset = 1.5;        ///< the element's own CSS border width
static const CGFloat kBrushCardTitleLeading = 111.0;     ///< border 1.5 + padding-left 109.5
static const CGFloat kBrushCardTitleTop = 32.0;          ///< border 1.5 + padding-top 30.5
static const CGFloat kBrushCardTitleLineHeight = 22.0;   ///< `.text_4-* { line-height: 22px }`

#pragma mark - Layer spec

@implementation BrushCardLayerSpec

+ (instancetype)layerNamed:(NSString *)assetName
               designFrame:(CGRect)designFrame
          parentDesignSize:(CGSize)parentDesignSize
               parentIndex:(NSInteger)parentIndex {
    BrushCardLayerSpec *spec = [[BrushCardLayerSpec alloc] init];
    spec->_assetName = [assetName copy];
    spec->_designFrame = designFrame;
    spec->_parentDesignSize = parentDesignSize;
    spec->_parentIndex = parentIndex;
    return spec;
}

@end

#pragma mark - Card

@interface BrushOptionCardView ()
@property(nonatomic, copy) NSString *optionLabel;
@property(nonatomic, copy) NSString *artName;
@property(nonatomic, assign) BOOL bordered;
@property(nonatomic, assign) CGSize designSize;
@property(nonatomic, assign) CGFloat artHeight;
@property(nonatomic, copy) NSArray<BrushCardLayerSpec *> *layerSpecs;
@property(nonatomic, strong) UIImageView *artView;
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UIView *ringView;
@property(nonatomic, strong) NSMutableArray<UIView *> *layerViews;
@end

@implementation BrushOptionCardView

+ (instancetype)cardWithIdentifier:(NSString *)identifier
                             title:(NSString *)title
                          artNamed:(NSString *)artNamed
                        designSize:(CGSize)designSize
                         artHeight:(CGFloat)artHeight
                          bordered:(BOOL)bordered
                        layerSpecs:(NSArray<BrushCardLayerSpec *> *)layerSpecs {
    BrushOptionCardView *card = [[BrushOptionCardView alloc] initWithFrame:CGRectZero];
    card.accessibilityIdentifier = identifier;
    card->_optionLabel = [title copy];
    card->_artName = [artNamed copy];
    card->_bordered = bordered;
    card->_designSize = designSize;
    card->_artHeight = artHeight;
    card->_layerSpecs = [layerSpecs copy] ?: @[];
    [card buildSubviews];
    return card;
}

- (instancetype)initWithCoder:(NSCoder *)coder {
    self = [super initWithCoder:coder];
    if (self) {
        [self buildSubviews];
    }
    return self;
}

- (void)buildSubviews {
    if (self.artView) {
        return;
    }

    self.backgroundColor = [UIColor colorWithRed:251 / 255.0 green:251 / 255.0 blue:251 / 255.0 alpha:1];
    self.layer.cornerRadius = kBrushCardCornerRadius;
    self.layer.masksToBounds = YES;

    CGSize design = self.designSize;
    NSString *prefix = self.accessibilityIdentifier ?: @"brushOptionCard";

    // --- artwork: full-bleed from the card's *padding* box, clipped by the card ---
    // CSS `background-origin` defaults to `padding-box` while `background-clip`
    // defaults to `border-box`: the image is positioned from the padding box (so it
    // starts one border-width inside the card) and then clipped by the border box.
    // Measured against the baseline, the card artwork really does sit ~1.3pt right
    // and ~1pt down from the card's outer top-left, which is this 1.5px inset.
    CGFloat artInset = self.bordered ? kBrushCardBorderInset : 0.0;
    self.artView = [[UIImageView alloc] initWithImage:[UIImage imageNamed:self.artName]];
    self.artView.contentMode = UIViewContentModeScaleToFill;
    self.artView.accessibilityIdentifier = [prefix stringByAppendingString:@".art"];
    [self addSubview:self.artView];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.artView
                                                                   parent:self
                                                              designFrame:CGRectMake(artInset,
                                                                                     artInset,
                                                                                     design.width,
                                                                                     self.artHeight)
                                                         parentDesignSize:design]];

    // --- nested decorative layers (Pastel smear chain) ---
    self.layerViews = [NSMutableArray array];
    for (BrushCardLayerSpec *spec in self.layerSpecs) {
        UIView *parent = (spec.parentIndex == NSNotFound || spec.parentIndex < 0)
            ? self
            : self.layerViews[(NSUInteger)spec.parentIndex];
        UIImageView *layer = [[UIImageView alloc] initWithImage:[UIImage imageNamed:spec.assetName]];
        layer.contentMode = UIViewContentModeScaleToFill;
        layer.accessibilityIdentifier =
            [prefix stringByAppendingFormat:@".layer%lu", (unsigned long)self.layerViews.count];
        [parent addSubview:layer];
        [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:layer
                                                                       parent:parent
                                                                  designFrame:spec.designFrame
                                                             parentDesignSize:spec.parentDesignSize]];
        [self.layerViews addObject:layer];
    }

    // --- title: intrinsic type, positioned by the design padding ---
    NSMutableParagraphStyle *style =
        [[BrushSelectionStyle paragraphStyleWithLineHeight:kBrushCardTitleLineHeight] mutableCopy];
    style.lineBreakMode = NSLineBreakByClipping;

    self.titleLabel = [[UILabel alloc] init];
    self.titleLabel.attributedText = [[NSAttributedString alloc] initWithString:self.optionLabel
                                                                    attributes:@{
        NSFontAttributeName: BrushSelectionStyle.cardTitleFont,
        NSForegroundColorAttributeName: BrushSelectionStyle.primaryTextColor,
        NSParagraphStyleAttributeName: style,
    }];
    self.titleLabel.numberOfLines = 1;
    self.titleLabel.textAlignment = NSTextAlignmentLeft;
    self.titleLabel.accessibilityIdentifier = [prefix stringByAppendingString:@".title"];
    [self addSubview:self.titleLabel];
    [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.titleLabel
                                                                   parent:self
                                                              designFrame:CGRectMake(kBrushCardTitleLeading,
                                                                                     kBrushCardTitleTop,
                                                                                     0,
                                                                                     0)
                                                         parentDesignSize:design
                                                                 sizeMode:BrushSelectionClosureSizeIntrinsic
                                                                   anchor:BrushSelectionClosureAnchorLeading]];

    // --- ring: drawn last so it sits above the artwork and the smear layers ---
    if (self.bordered) {
        self.ringView = [[UIView alloc] initWithFrame:CGRectZero];
        self.ringView.backgroundColor = UIColor.clearColor;
        self.ringView.userInteractionEnabled = NO;
        self.ringView.layer.cornerRadius = kBrushCardCornerRadius;
        self.ringView.layer.borderWidth = kBrushCardRingWidth;
        self.ringView.layer.borderColor = BrushSelectionStyle.cardBorderColor.CGColor;
        self.ringView.accessibilityIdentifier = [prefix stringByAppendingString:@".ring"];
        [self addSubview:self.ringView];
        [NSLayoutConstraint activateConstraints:[BrushSelectionStyle closeChild:self.ringView
                                                                       parent:self
                                                                  designFrame:CGRectMake(0, 0, design.width, design.height)
                                                             parentDesignSize:design]];
    }

    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleTap:)];
    [self addGestureRecognizer:tap];
}

- (void)handleTap:(UITapGestureRecognizer *)recognizer {
    if (self.onTap) {
        self.onTap(self);
    }
}

@end
