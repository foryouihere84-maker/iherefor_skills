//
//  StyleSelectionOptionCardView.h
//  testUIProject
//
//  One selectable style option: the artwork image, an optional dark chip scrim that
//  carries the label, the label itself and the selection ring.
//
//  Kept as a real view hierarchy rather than a flattened image so the label stays
//  accessible and the selected state stays testable.
//

#import <UIKit/UIKit.h>
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

/// The eight options offered by the page, in design order.
typedef NS_ENUM(NSInteger, StyleSelectionOption) {
    StyleSelectionOptionNone = 0,
    StyleSelectionOptionAnimal,
    StyleSelectionOptionManga,
    StyleSelectionOptionPeople,
    StyleSelectionOptionCute,
    StyleSelectionOptionFood,
    StyleSelectionOptionMandala,
    StyleSelectionOptionFlower,
    StyleSelectionOptionEasy,
};

/// Design size of every option card: .group_5 / .group_6 / .section_* /
/// .text-wrapper_6 / _8 / _10 all resolve to 170x146 on the Lanhu canvas.
extern const CGSize kStyleSelectionCardDesignSize;

/// Design frame of the chip scrim inside a card. .text-wrapper_3 / _4 / _5 / _7 / _9
/// all resolve to this box, so one image serves five positions.
extern const CGRect kStyleSelectionChipScrimDesignFrame;

/// Design frame of the selection ring: .box_3 is 173x149, i.e. the card grown by the
/// 1.5pt stroke on every side.
extern const CGRect kStyleSelectionSelectionRingDesignFrame;

@interface StyleSelectionOptionCardView : UIControl

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                       option:(StyleSelectionOption)option
                          art:(NSString *)artImageName
                    chipScrim:(nullable NSString *)chipScrimImageName
                        label:(NSString *)label
             labelDesignFrame:(CGRect)labelDesignFrame
               labelStyleName:(NSString *)labelStyleName
                  weightClass:(StyleSelectionFontWeightClass)weightClass;

@property(nonatomic, assign) StyleSelectionOption option;

/// Drives the violet 1.5pt ring. The ring is larger than the card, so the card must
/// not clip its bounds.
@property(nonatomic, assign, getter=isRingVisible) BOOL ringVisible;

@end

NS_ASSUME_NONNULL_END
