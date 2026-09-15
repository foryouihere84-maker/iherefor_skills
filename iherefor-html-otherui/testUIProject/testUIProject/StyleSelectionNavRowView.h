//
//  StyleSelectionNavRowView.h
//  testUIProject
//
//  The navigation row: back control, step progress and the Skip action.
//  Design size 361x32 (index.css .section_6, which sits 18pt below the status band).
//

#import <UIKit/UIKit.h>
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface StyleSelectionNavRowView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style;

/// The owner connects the named handlers to these controls.
@property(nonatomic, strong, readonly) UIButton *backButton;
@property(nonatomic, strong, readonly) UIButton *skipButton;
@property(nonatomic, strong, readonly) UIView *progressTrackView;
@property(nonatomic, strong, readonly) UIView *progressFillView;

/// Width of the filled segment, stated in Lanhu design points out of the 232pt track
/// (the design shows 24pt). Converted to a multiplier of the track width, so the bar
/// keeps its proportion on any screen instead of freezing a device length.
- (void)setProgressFillDesignWidth:(CGFloat)designWidth;

@end

NS_ASSUME_NONNULL_END
