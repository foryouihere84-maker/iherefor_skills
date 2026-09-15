//
//  PaletteCardView.h
//  testUIProject
//
//  A single palette card in the Lanhu "色板" (Palette) design: a rounded white card
//  with a category title and a swatch-strip image. Supports a "selected" state that
//  paints the accent border (Basic is selected on launch).
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface PaletteCardView : UIView

/// Card design frame in the 393x852 board space (x, y, width, height).
@property(nonatomic, assign) CGRect designFrame;

@property(nonatomic, copy, nullable) NSString *title;
@property(nonatomic, copy, nullable) NSString *swatchImageName;

@property(nonatomic, assign) BOOL selected;

@end

NS_ASSUME_NONNULL_END
