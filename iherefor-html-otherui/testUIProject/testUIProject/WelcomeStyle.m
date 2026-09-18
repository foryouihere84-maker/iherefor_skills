//
//  WelcomeStyle.m
//  testUIProject
//
//  欢迎页设计 token 实现。字号 / 颜色取设计稿封闭值。
//

#import "WelcomeStyle.h"

@implementation WelcomeStyle

#pragma mark - 颜色

+ (UIColor *)textColor { return [UIColor colorWithRed:22/255.0 green:22/255.0 blue:22/255.0 alpha:1.0]; }

#pragma mark - 字体

+ (UIFont *)titleFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Avenir-Black" size:size];
    if (!f) { f = [UIFont fontWithName:@"Avenir-Heavy" size:size]; }
    if (!f) { f = [UIFont systemFontOfSize:size weight:UIFontWeightHeavy]; }
    return f;
}

+ (UIFont *)subtitleFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Avenir-Medium" size:size];
    if (!f) { f = [UIFont systemFontOfSize:size weight:UIFontWeightMedium]; }
    return f;
}

#pragma mark - 字号（双稿 design 值）

+ (CGFloat)titleFontSizePhone    { return 28.0; }
+ (CGFloat)titleFontSizeIpad     { return 36.0; }
+ (CGFloat)subtitleFontSizePhone { return 22.0; }
+ (CGFloat)subtitleFontSizeIpad  { return 30.0; }

#pragma mark - 行高（双稿 design 值）

+ (CGFloat)titleLineHeightPhone    { return 34.0; }
+ (CGFloat)titleLineHeightIpad     { return 43.0; }
+ (CGFloat)subtitleLineHeightPhone { return 26.0; }
+ (CGFloat)subtitleLineHeightIpad  { return 36.0; }

#pragma mark - 间距（双稿 design 值）

+ (CGFloat)titleToSubtitleGapPhone { return 12.0; }
+ (CGFloat)titleToSubtitleGapIpad  { return 14.0; }

#pragma mark - 标题字距（负，双稿值）

+ (CGFloat)titleLetterSpacingPhone { return -0.48; }
+ (CGFloat)titleLetterSpacingIpad  { return -0.62; }

#pragma mark - 文字组的纵向位置（页面高度比例）

// 稿件实测：356/852 = 0.417840、423.5/1080 = 0.392130（组 centerY ÷ 页面高）。
+ (CGFloat)textGroupCenterYRatioPhone { return 356.0 / 852.0; }
+ (CGFloat)textGroupCenterYRatioIpad  { return 423.5 / 1080.0; }

@end
