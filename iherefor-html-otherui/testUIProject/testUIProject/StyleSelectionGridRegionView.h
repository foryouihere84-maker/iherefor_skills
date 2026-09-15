//
//  StyleSelectionGridRegionView.h
//  testUIProject
//
//  The lower canvas region (.section_8): three option rows plus the footer overlay.
//  Design size 393x487, so it starts exactly where the hero region ends.
//

#import <UIKit/UIKit.h>
#import "StyleSelectionFooterView.h"
#import "StyleSelectionOptionRowView.h"
#import "StyleSelectionStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface StyleSelectionGridRegionView : UIView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                         rows:(NSArray<StyleSelectionOptionRowView *> *)rows
                       footer:(StyleSelectionFooterView *)footer;

@property(nonatomic, copy, readonly) NSArray<StyleSelectionOptionRowView *> *rows;
@property(nonatomic, strong, readonly) StyleSelectionFooterView *footerView;

@end

NS_ASSUME_NONNULL_END
