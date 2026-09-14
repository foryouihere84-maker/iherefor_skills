//
//  SpecialOfferPlanCardView.h
//  testUIProject
//
//  One selectable plan row inside the offers block: background artwork plus the
//  plan title, price and secondary note. Kept as a real view hierarchy (not a
//  flattened image) so the text stays accessible and testable.
//

#import <UIKit/UIKit.h>
#import "SpecialOfferStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface SpecialOfferPlanCardView : UIControl

- (instancetype)initWithStyle:(SpecialOfferStyle *)style
                 canvasFrame:(CGRect)canvasFrame
            backgroundImage:(nullable NSString *)backgroundImageName
                        title:(NSString *)title
                        price:(NSString *)price
                         note:(nullable NSString *)note;

/// Optional struck-through price note (the weekly card shows $7.99/week).
@property(nonatomic, copy, nullable) NSString *struckPriceText;

@end

NS_ASSUME_NONNULL_END
