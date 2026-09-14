//
//  SpecialOfferPrimaryButton.h
//  testUIProject
//
//  "Claim My Offer" call to action: a pill button whose background comes from the
//  Lanhu export (special_offer_cta_background) drawn into the mapped bounds.
//

#import <UIKit/UIKit.h>
#import "SpecialOfferStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface SpecialOfferPrimaryButton : UIButton

- (instancetype)initWithStyle:(SpecialOfferStyle *)style canvasFrame:(CGRect)canvasFrame;

@property(nonatomic, readonly) CGRect canvasFrame;

@end

NS_ASSUME_NONNULL_END
