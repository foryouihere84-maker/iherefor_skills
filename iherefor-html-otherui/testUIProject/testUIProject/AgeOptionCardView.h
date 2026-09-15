//
//  AgeOptionCardView.h
//  testUIProject
//
//  A single age-option card for the Lanhu "年龄" (Age) design. Renders an emoji
//  glyph plus a label inside a rounded, bordered card; toggles a violet
//  selection border when selected.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// A rounded card showing one age band (e.g. "✏️ Less than 14").
@interface AgeOptionCardView : UIView

/// Creates a card with the given emoji and label.
/// @param emoji Prefix glyph rendered in the emoji font (e.g. @"✏️").
/// @param label Option text rendered in Avenir-Medium 18 (e.g. @"Less than 14").
- (instancetype)initWithEmoji:(NSString *)emoji label:(NSString *)label;

/// Emoji glyph shown at the card's leading edge.
@property(nonatomic, copy, readonly) NSString *emoji;

/// Option label text.
@property(nonatomic, copy, readonly) NSString *optionLabel;

/// Toggles the selection state: the border switches between the violet
/// selected colour and the grey idle colour.
@property(nonatomic, assign, getter=isSelectedState) BOOL selectedState;

/// Tap callback. Fired when the card is tapped (target-action internal).
@property(nonatomic, copy, nullable) void (^onTap)(AgeOptionCardView *card);

@end

NS_ASSUME_NONNULL_END
