//
//  SpecialOfferPrimaryButton.m
//  testUIProject
//

#import "SpecialOfferPrimaryButton.h"

static NSString *const kSpecialOfferCTAAssetName = @"special_offer_cta_background";
/// .text_10 "Claim My Offer" - reference advance width 143.0pt at CSS 20px.
static NSString *const kSpecialOfferCTATitle = @"Claim My Offer";

@implementation SpecialOfferPrimaryButton

- (instancetype)initWithStyle:(SpecialOfferStyle *)style canvasFrame:(CGRect)canvasFrame {
    self = [super initWithFrame:[style mappedRect:canvasFrame]];
    if (self) {
        _canvasFrame = canvasFrame;
        self.translatesAutoresizingMaskIntoConstraints = YES;
        self.accessibilityIdentifier = @"special-offer-claim-offer";
        self.titleLabel.font = [SpecialOfferStyle fontForText:kSpecialOfferCTATitle
                                                       class:SpecialOfferFontWeightClassBlack
                                                   pointSize:[style mappedLength:20]
                                              referenceWidth:143.0 * style.canvasScale.x];
        [self setTitleColor:SpecialOfferStyle.onAccentTextColor forState:UIControlStateNormal];
        [self setTitle:@"Claim My Offer" forState:UIControlStateNormal];
        self.layer.cornerRadius = [style mappedLength:34];
        self.clipsToBounds = YES;

        UIImage *background = [UIImage imageNamed:kSpecialOfferCTAAssetName];
        if (!background) {
            NSString *path = [[NSBundle mainBundle] pathForResource:kSpecialOfferCTAAssetName ofType:@"png"];
            if (path.length) {
                background = [UIImage imageWithContentsOfFile:path];
            }
        }
        // The export is a 1x pill; stretch it to the mapped frame so the drawn
        // content scales with the same scaleX/scaleY as the frame.
        if (background) {
            [self setBackgroundImage:background forState:UIControlStateNormal];
            self.contentHorizontalAlignment = UIControlContentHorizontalAlignmentCenter;
        }
        NSLog(@"IHEREFOR_IMAGE_FRAME name=%@ x=%.3f y=%.3f w=%.3f h=%.3f naturalW=%.0f naturalH=%.0f contentMode=UIViewContentModeScaleToFill",
              kSpecialOfferCTAAssetName, self.frame.origin.x, self.frame.origin.y,
              self.frame.size.width, self.frame.size.height,
              background.size.width, background.size.height);
    }
    return self;
}

@end
