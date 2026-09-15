//
//  BrushOptionCardView.h
//  testUIProject
//
//  One brush-option card for the Lanhu "笔刷" (Brush) design. The exported DOM is
//  `.list-items_1-* > .text-wrapper_2-* > span.text_4-*`: an outer box carrying the
//  card artwork, an inner box carrying the title, and (on the Pastel card only) a
//  chain of nested smear layers `.box_4 > .box_5 > .image-wrapper_1 > .image_2`.
//
//  The artwork PNGs already bake in the card body, its corner radius and a 1px
//  border, so this view paints the art as a full-bleed image and then draws a
//  single ring on top. The export paints that ring twice (outer `.list-items_*`
//  1.5px + inner `.text-wrapper_*` 1.5px offset by 1px); collapsing the two
//  same-coloured, overlapping rings into one 2.5pt ring reproduces the band the
//  baseline actually shows — see ui-implementation-plan.json -> unsupported.
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

/// A nested decorative layer inside an option card, mirroring the exported DOM
/// nesting. `parentIndex` is the index of the layer this one is a child of, or
/// `NSNotFound` when the layer's parent is the card itself — the same
/// parentIndex relation recorded in reference/page-facts.json.
@interface BrushCardLayerSpec : NSObject

+ (instancetype)layerNamed:(NSString *)assetName
               designFrame:(CGRect)designFrame
          parentDesignSize:(CGSize)parentDesignSize
               parentIndex:(NSInteger)parentIndex;

@property(nonatomic, copy, readonly) NSString *assetName;
@property(nonatomic, assign, readonly) CGRect designFrame;
/// Design size of this layer's *immediate* parent, not of the card.
@property(nonatomic, assign, readonly) CGSize parentDesignSize;
@property(nonatomic, assign, readonly) NSInteger parentIndex;

@end

/// A brush option card: artwork, title, optional ring, optional smear layers.
@interface BrushOptionCardView : UIView

/// @param identifier  Accessibility identifier for the card, e.g. @"brushSelection.card0".
///                    Child views derive their own identifiers from it.
/// @param title       Card label, e.g. @"Paint Brush".
/// @param artNamed    Asset name of the card artwork (natural size 353 x artHeight).
/// @param designSize  Design frame size of the card body, e.g. (353, 87).
/// @param artHeight   Natural height of the artwork, e.g. 86. The art is anchored at
///                    the card's top-left at its natural size and clipped by the
///                    card, which is what `background` + `overflow: hidden` does.
/// @param bordered    NO for the borderless Flat Brush card.
/// @param layerSpecs  Nested decorative layers, or nil.
+ (instancetype)cardWithIdentifier:(NSString *)identifier
                             title:(NSString *)title
                          artNamed:(NSString *)artNamed
                        designSize:(CGSize)designSize
                         artHeight:(CGFloat)artHeight
                          bordered:(BOOL)bordered
                        layerSpecs:(nullable NSArray<BrushCardLayerSpec *> *)layerSpecs;

@property(nonatomic, copy, readonly) NSString *optionLabel;
@property(nonatomic, copy, readonly) NSString *artName;
@property(nonatomic, assign, readonly) BOOL bordered;

/// Tap callback. Fired when the card is tapped (target-action internal).
@property(nonatomic, copy, nullable) void (^onTap)(BrushOptionCardView *card);

@end

NS_ASSUME_NONNULL_END
