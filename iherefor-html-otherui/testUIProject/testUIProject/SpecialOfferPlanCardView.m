//
//  SpecialOfferPlanCardView.m
//  testUIProject
//

#import "SpecialOfferPlanCardView.h"

@interface SpecialOfferPlanCardView ()
@property(nonatomic, strong) SpecialOfferStyle *style;
@property(nonatomic, strong) UIImageView *backgroundImageView;
@property(nonatomic, strong) UILabel *titleLabel;
@property(nonatomic, strong) UILabel *priceLabel;
@property(nonatomic, strong) UILabel *noteLabel;
@end

@implementation SpecialOfferPlanCardView

- (instancetype)initWithStyle:(SpecialOfferStyle *)style
                 canvasFrame:(CGRect)canvasFrame
            backgroundImage:(NSString *)backgroundImageName
                        title:(NSString *)title
                        price:(NSString *)price
                         note:(NSString *)note {
    self = [super initWithFrame:[style mappedRect:canvasFrame]];
    if (self) {
        _style = style;

        self.translatesAutoresizingMaskIntoConstraints = YES;
        self.clipsToBounds = NO;

        _backgroundImageView = [[UIImageView alloc] initWithFrame:self.bounds];
        _backgroundImageView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        _backgroundImageView.contentMode = UIViewContentModeScaleToFill;
        _backgroundImageView.clipsToBounds = YES;
        _backgroundImageView.layer.contents = (id)_backgroundImageView.image.CGImage;
        _backgroundImageView.layer.contentsGravity = kCAGravityResize;

        UIImage *background = nil;
        if (backgroundImageName.length) {
            background = [UIImage imageNamed:backgroundImageName];
            if (!background) {
                NSString *path = [[NSBundle mainBundle] pathForResource:backgroundImageName ofType:@"png"];
                if (path.length) {
                    background = [UIImage imageWithContentsOfFile:path];
                }
            }
        }
        _backgroundImageView.image = background;
        _backgroundImageView.layer.contents = (id)background.CGImage;
        [self addSubview:_backgroundImageView];

        _titleLabel = [self labelWithCanvasFrame:CGRectMake(15.0, 16.0, 150.0, 22.0)
                                       pointSize:16.0
                                          weight:UIFontWeightBlack
                                            text:title
                                       styleName:@"planTitleWeekly"];
        _titleLabel.text = title;
        _titleLabel.accessibilityIdentifier = @"special-offer-plan-title";
        [self addSubview:_titleLabel];

        // .text-wrapper_2 sits at canvas y=513 (card y=495), .text-wrapper_6 at
        // y=531; the 22pt tall column box is how the browser resolved the
        // 15pt-tall line boxes inside the space-between flex row.
        _priceLabel = [self labelWithCanvasFrame:CGRectMake(200.0, 16.0, 132.0, 22.0)
                                       pointSize:10.0
                                          weight:UIFontWeightMedium
                                            text:price
                                       styleName:@"planPriceCurrent"];
        _priceLabel.text = price;
        _priceLabel.textAlignment = NSTextAlignmentRight;
        [self addSubview:_priceLabel];

        _noteLabel = [self labelWithCanvasFrame:CGRectMake(180.0, 45.0, 152.0, 14.0)
                                      pointSize:10.0
                                         weight:UIFontWeightMedium
                                           text:note
                                      styleName:@"planNote"];
        _noteLabel.text = note;
        _noteLabel.textAlignment = NSTextAlignmentRight;
        [self addSubview:_noteLabel];

        NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ x=%.3f y=%.3f w=%.3f h=%.3f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
              backgroundImageName ?: @"<none>", self.frame.origin.x, self.frame.origin.y,
              self.frame.size.width, self.frame.size.height,
              background.size.width, background.size.height);
    }
    return self;
}

- (UILabel *)labelWithCanvasFrame:(CGRect)canvasFrame
                        pointSize:(CGFloat)pointSize
                           weight:(UIFontWeight)weight
                             text:(NSString *)text
                        styleName:(NSString *)styleName {
    UILabel *label = [[UILabel alloc] initWithFrame:[self.style mappedRect:canvasFrame]];
    label.font = [SpecialOfferStyle fontForText:text ?: @""
                                          class:(weight >= UIFontWeightBlack ? SpecialOfferFontWeightClassBlack : SpecialOfferFontWeightClassMedium)
                                      pointSize:[self.style mappedLength:pointSize]
                                 referenceWidth:[SpecialOfferStyle referenceWidthForStyle:styleName] * self.style.canvasScale.x];
    label.textColor = SpecialOfferStyle.planDetailColor;
    label.numberOfLines = 1;
    label.lineBreakMode = NSLineBreakByClipping;
    label.translatesAutoresizingMaskIntoConstraints = YES;
    return label;
}

- (void)setStruckPriceText:(NSString *)struckPriceText {
    _struckPriceText = [struckPriceText copy];
    if (!struckPriceText.length) {
        self.noteLabel.attributedText = nil;
        return;
    }
    // The struck price is its own text element in index.css (.text-wrapper_6 ->
    // .text_16 + .text_17) with its own measured reference advance width.
    self.noteLabel.font = [SpecialOfferStyle fontForText:struckPriceText
                                                   class:SpecialOfferFontWeightClassMedium
                                               pointSize:[self.style mappedLength:10.0]
                                          referenceWidth:[SpecialOfferStyle referenceWidthForStyle:@"planPriceStruck"] * self.style.canvasScale.x];
    NSDictionary *attributes = @{
        NSFontAttributeName : self.noteLabel.font,
        NSForegroundColorAttributeName : SpecialOfferStyle.planDetailColor,
        NSStrikethroughStyleAttributeName : @(NSUnderlineStyleSingle),
        NSStrikethroughColorAttributeName : SpecialOfferStyle.planDetailColor,
    };
    self.noteLabel.attributedText = [[NSAttributedString alloc] initWithString:struckPriceText attributes:attributes];
}

- (void)setSelected:(BOOL)selected {
    [super setSelected:selected];
    self.backgroundImageView.alpha = selected ? 1.0 : 0.99;
}

@end
