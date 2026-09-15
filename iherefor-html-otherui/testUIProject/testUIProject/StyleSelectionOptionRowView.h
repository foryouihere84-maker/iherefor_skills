//
//  StyleSelectionOptionRowView.h
//  testUIProject
//
//  One row of the style grid: two option cards side by side. The row knows its own
//  Lanhu design size (353x146) and places the two 170x146 cards with multipliers, so
//  no device point ever reaches the constraint.
//

#import <UIKit/UIKit.h>
#import "StyleSelectionOptionCardView.h"
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

/// Declarative description of one option. The label frame is relative to the chip
/// scrim when one is supplied, otherwise relative to the card.
@interface StyleSelectionOptionSpec : NSObject

@property(nonatomic, assign) StyleSelectionOption option;
@property(nonatomic, copy) NSString *art;
@property(nonatomic, copy, nullable) NSString *chipScrim;
@property(nonatomic, copy) NSString *label;
@property(nonatomic, assign) CGRect labelDesignFrame;
@property(nonatomic, copy) NSString *labelStyleName;
@property(nonatomic, assign) StyleSelectionFontWeightClass weightClass;
@property(nonatomic, copy) NSString *accessibilityIdentifier;

+ (instancetype)specWithOption:(StyleSelectionOption)option
                           art:(NSString *)art
                     chipScrim:(nullable NSString *)chipScrim
                         label:(NSString *)label
              labelDesignFrame:(CGRect)labelDesignFrame
                labelStyleName:(NSString *)labelStyleName
                   weightClass:(StyleSelectionFontWeightClass)weightClass
       accessibilityIdentifier:(NSString *)accessibilityIdentifier;

@end

/// Design size of a grid row (index.css .section_7 / .group_7 / _8 / _9).
extern const CGSize kStyleSelectionRowDesignSize;

@interface StyleSelectionOptionRowView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                         left:(StyleSelectionOptionSpec *)left
                        right:(StyleSelectionOptionSpec *)right;

/// Card views in design order, so the owner can drive the selection ring.
@property(nonatomic, copy, readonly) NSArray<StyleSelectionOptionCardView *> *cards;

/// The card standing for `option`, or nil.
- (nullable StyleSelectionOptionCardView *)cardForOption:(StyleSelectionOption)option;

@end

NS_ASSUME_NONNULL_END
