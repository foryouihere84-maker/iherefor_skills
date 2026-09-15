//
//  StyleSelectionFooterView.h
//  testUIProject
//
//  The bottom region (.group_10): the gradient scrim that fades the grid out, plus the
//  primary CTA. Design size 393x190, absolutely positioned 297pt below the top of the
//  lower canvas region.
//

#import <UIKit/UIKit.h>
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface StyleSelectionFooterView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style;

@property(nonatomic, strong, readonly) UIImageView *scrimImageView;
@property(nonatomic, strong, readonly) UIButton *continueButton;
@property(nonatomic, strong, readonly) UILabel *continueLabel;

@end

NS_ASSUME_NONNULL_END
