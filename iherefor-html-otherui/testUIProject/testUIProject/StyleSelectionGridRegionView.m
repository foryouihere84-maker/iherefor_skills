//
//  StyleSelectionGridRegionView.m
//  testUIProject
//

#import "StyleSelectionGridRegionView.h"

/// index.css .section_8 covers everything below .box_1. The canvas is 852pt tall and
/// the hero is 365pt, so the region is 393x487 and its bottom meets the canvas bottom
/// exactly. (The measured 488 in page-facts.json is the browser's sub-pixel flex
/// rounding after the 1.0229 canvas scale.)
static const CGSize kGridRegionDesignSize = {393.0, 487.0};

/// Two 170x146 rows separated by a 13pt design constant; .section_8 pads 20pt
/// horizontally, so every row starts 20pt in and is 353pt wide.
static const CGFloat kRowLeadingDesign = 20.0;
static const CGFloat kRowTopDesign[3] = {0.0, 159.0, 318.0};

/// .group_10 is absolutely positioned 297pt below the region top (canvas y=662).
static const CGRect kFooterDesignFrame = {{0.0, 297.0}, {393.0, 190.0}};

@interface StyleSelectionGridRegionView ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, copy) NSArray<StyleSelectionOptionRowView *> *rows;
@property(nonatomic, strong) StyleSelectionFooterView *footerView;
@end

@implementation StyleSelectionGridRegionView

- (instancetype)initWithStyle:(StyleSelectionStyle *)style
                         rows:(NSArray<StyleSelectionOptionRowView *> *)rows
                       footer:(StyleSelectionFooterView *)footer {
    self = [super initWithFrame:CGRectZero];
    if (self) {
        _style = style;
        _rows = [rows copy];
        _footerView = footer;
        self.translatesAutoresizingMaskIntoConstraints = NO;
        self.clipsToBounds = YES;
        self.backgroundColor = StyleSelectionStyle.pageBackgroundColor;

        NSUInteger index = 0;
        for (StyleSelectionOptionRowView *row in _rows) {
            CGFloat top = index < 3 ? kRowTopDesign[index] : (index * (146.0 + 13.0));
            CGRect frame = CGRectMake(kRowLeadingDesign, top,
                                      kStyleSelectionRowDesignSize.width,
                                      kStyleSelectionRowDesignSize.height);
            [self addSubview:row];
            [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:row
                                                                           parent:self
                                                                      designFrame:frame
                                                                 parentDesignSize:kGridRegionDesignSize]];
            index += 1;
        }

        // Added last: .group_10 overlaps the third row, which is exactly what the
        // gradient scrim is for.
        [self addSubview:_footerView];
        [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:_footerView
                                                                       parent:self
                                                                  designFrame:kFooterDesignFrame
                                                             parentDesignSize:kGridRegionDesignSize]];

        NSLog(@"IHEREFOR_REGION_FRAME name=StyleSelectionGridRegionView designW=%.0f designH=%.0f rows=%lu "
              @"rowTopDesign=%.0f,%.0f,%.0f footerTopDesign=%.0f clipsToBounds=YES",
              kGridRegionDesignSize.width, kGridRegionDesignSize.height,
              (unsigned long)_rows.count,
              kRowTopDesign[0], kRowTopDesign[1], kRowTopDesign[2],
              kFooterDesignFrame.origin.y);
    }
    return self;
}

@end
