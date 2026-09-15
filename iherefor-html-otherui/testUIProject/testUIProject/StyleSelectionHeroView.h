//
//  StyleSelectionHeroView.h
//  testUIProject
//
//  The upper canvas region (.box_1): soft wash artwork, navigation row, headline and
//  the first row of options. Design size 393x365.
//

#import <UIKit/UIKit.h>
#import "StyleSelectionHeadlineView.h"
#import "StyleSelectionNavRowView.h"
#import "StyleSelectionOptionRowView.h"
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface StyleSelectionHeroView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
             topOptionRowView:(StyleSelectionOptionRowView *)optionRowView;

@property(nonatomic, strong, readonly) UIImageView *washImageView;
@property(nonatomic, strong, readonly) StyleSelectionNavRowView *navRowView;
@property(nonatomic, strong, readonly) StyleSelectionHeadlineView *headlineView;
@property(nonatomic, strong, readonly) StyleSelectionOptionRowView *optionRowView;

@end

NS_ASSUME_NONNULL_END
