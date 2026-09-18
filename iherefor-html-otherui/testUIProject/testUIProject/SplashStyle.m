//
//  SplashStyle.m
//  testUIProject
//
//  启屏页设计 token 实现。颜色 / 字号 / 尺寸全部取设计稿封闭值。
//

#import "SplashStyle.h"

@implementation SplashStyle

#pragma mark - 颜色

+ (UIColor *)brandTextColor       { return [UIColor colorWithRed:20/255.0 green:20/255.0 blue:20/255.0 alpha:1.0]; }
+ (UIColor *)brandTextShadowColor { return [UIColor colorWithRed:86/255.0 green:116/255.0 blue:255/255.0 alpha:0.16]; }
+ (CGSize)brandTextShadowOffset   { return CGSizeMake(0.0, 2.0); }

#pragma mark - 字体

+ (UIFont *)brandFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Futura-Medium" size:size];
    if (f) { return f; }
    // Futura-Medium 缺失时退化系统字体（中粗，保持视觉重量接近）
    return [UIFont systemFontOfSize:size weight:UIFontWeightMedium];
}

#pragma mark - 字号（双稿 design 值）

+ (CGFloat)brandFontSizePhone { return 20.0; }
+ (CGFloat)brandFontSizeIpad  { return 26.0; }

#pragma mark - Logo 图标尺寸（双稿 design 值）

+ (CGFloat)logoSizePhone { return 108.0; }
+ (CGFloat)logoSizeIpad  { return 144.0; }

#pragma mark - Logo 到文字间距（双稿 design 值）

+ (CGFloat)logoToTextGapPhone { return 12.0; }
+ (CGFloat)logoToTextGapIpad  { return 13.0; }

#pragma mark - Logo 组的纵向位置（页面高度比例）

// 稿件实测：353/852 = 0.414319、423.5/1080 = 0.392130（组 centerY ÷ 页面高）。
+ (CGFloat)logoGroupCenterYRatioPhone { return 353.0 / 852.0; }
+ (CGFloat)logoGroupCenterYRatioIpad  { return 423.5 / 1080.0; }

@end
