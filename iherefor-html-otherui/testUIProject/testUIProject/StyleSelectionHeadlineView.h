//
//  StyleSelectionHeadlineView.h
//  testUIProject
//
//  The two-line, right-aligned headline plus the full-width question mark.
//  Design size 328x62 (index.css .text-wrapper_2).
//

#import <UIKit/UIKit.h>
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface StyleSelectionHeadlineView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style;

/// Two lines, right-aligned: line 1 is the question, line 2 is "coloring" + ？.
@property(nonatomic, strong, readonly) UILabel *questionLabel;
@property(nonatomic, strong, readonly) UILabel *markLabel;

@end

NS_ASSUME_NONNULL_END
