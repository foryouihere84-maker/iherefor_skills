//
//  PaywallStyle.m
//  testUIProject
//
//  设计 token 实现。颜色 / 字号 / 圆角 / 描边全部取设计稿封闭值。
//

#import "PaywallStyle.h"

@implementation PaywallStyle

#pragma mark - 颜色

+ (UIColor *)pageBackground      { return [UIColor colorWithRed:241/255.0 green:240/255.0 blue:242/255.0 alpha:1.0]; }
+ (UIColor *)titleColor          { return [UIColor colorWithRed:22/255.0 green:22/255.0 blue:22/255.0 alpha:1.0]; }
+ (UIColor *)cardInk             { return [UIColor colorWithRed:20/255.0 green:20/255.0 blue:20/255.0 alpha:1.0]; }
+ (UIColor *)cardBorderMuted     { return [UIColor colorWithRed:215/255.0 green:215/255.0 blue:215/255.0 alpha:1.0]; }
+ (UIColor *)cardBorderSelected  { return [UIColor colorWithRed:20/255.0 green:20/255.0 blue:20/255.0 alpha:1.0]; }
+ (UIColor *)accent              { return [UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1.0]; }
+ (UIColor *)footerLink          { return [UIColor colorWithRed:152/255.0 green:151/255.0 blue:149/255.0 alpha:1.0]; }
+ (UIColor *)closeButtonFill     { return [UIColor colorWithRed:216/255.0 green:216/255.0 blue:216/255.0 alpha:1.0]; }
+ (UIColor *)closeButtonBorder   { return [UIColor colorWithRed:151/255.0 green:151/255.0 blue:151/255.0 alpha:1.0]; }

#pragma mark - 字体

// 首选 Avenir 族（iOS 内置），带兜底：AvenirLT-* 在 iOS 不存在，映射到 Avenir-*。
// 兜底字重按各自的设计字重给，否则「Heavy」会在缺字体时退化成和 Medium 一样的中粗，
// 卡片标题与价格就分不出来了。
static UIFont *_font(NSString *name, CGFloat size, UIFontWeight fallbackWeight) {
    UIFont *f = [UIFont fontWithName:name size:size];
    if (f) { return f; }
    return [UIFont systemFontOfSize:size weight:fallbackWeight];
}

+ (UIFont *)titleFont    { return _font(@"Avenir-Black",  [self titleFontSize],    UIFontWeightHeavy); }
+ (UIFont *)subtitleFont { return _font(@"Avenir-Medium", [self subtitleFontSize], UIFontWeightMedium); }
+ (UIFont *)cardTitleFont{ return _font(@"Avenir-Heavy",  [self cardTitleFontSize],UIFontWeightHeavy); }
+ (UIFont *)cardBodyFont { return _font(@"Avenir-Medium", [self cardBodyFontSize], UIFontWeightMedium); }
+ (UIFont *)badgeFont    { return _font(@"Avenir-Heavy",  [self cardBodyFontSize], UIFontWeightHeavy); }
+ (UIFont *)ctaFont      { return _font(@"Avenir-Heavy",  [self ctaFontSize],      UIFontWeightHeavy); }
+ (UIFont *)footerFont   { return _font(@"Avenir-Medium", [self footerFontSize],   UIFontWeightMedium); }

#pragma mark - 字号

+ (CGFloat)titleFontSize    { return 24.0; }
+ (CGFloat)subtitleFontSize { return 15.0; }
+ (CGFloat)cardTitleFontSize{ return 16.0; }
+ (CGFloat)cardBodyFontSize { return 10.0; }
+ (CGFloat)ctaFontSize      { return 20.0; }
+ (CGFloat)footerFontSize   { return 12.0; }

#pragma mark - 行高（稿件 font.line 实测）

+ (CGFloat)titleLineHeight     { return 29.0; }
+ (CGFloat)subtitleLineHeight  { return 18.0; }
+ (CGFloat)cardTitleLineHeight { return 22.0; }
+ (CGFloat)cardBodyLineHeight  { return 14.0; }
+ (CGFloat)ctaLineHeight       { return 27.0; }
+ (CGFloat)footerLineHeight    { return 16.0; }

+ (CGFloat)cardBodyAlpha { return 0.6; }

#pragma mark - 圆角与描边

+ (CGFloat)cardCornerRadius  { return 16.0; }
+ (CGFloat)ctaCornerRadius   { return 34.0; }
+ (CGFloat)badgeCornerRadius { return 6.0; }
+ (CGFloat)cardBorderWidth   { return 2.0; }
+ (CGFloat)closeButtonBorderWidth { return 2.0; }

#pragma mark - 几何

+ (CGFloat)maxContentWidth       { return 480.0; }
+ (CGFloat)contentHorizontalInset{ return 23.0; }
+ (CGFloat)heroHeight            { return 321.0; }
+ (CGFloat)cardHeight            { return 68.0; }
+ (CGFloat)ctaHeight             { return 68.0; }

@end
