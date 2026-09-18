//
//  WelcomeStyle.h
//  testUIProject
//
//  欢迎页设计 token。字号 / 颜色取设计稿封闭值，双稿（iPhone/iPad）各自取值。
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface WelcomeStyle : NSObject

#pragma mark - 颜色

/// 欢迎文字颜色 rgba(22,22,22,1)
+ (UIColor *)textColor;

#pragma mark - 字体（AvenirLT-* 在 iOS 映射到 Avenir-*）

/// 标题字族（AvenirLT-Black → Avenir-Black）
+ (UIFont *)titleFontOfSize:(CGFloat)size;
/// 副标题字族（AvenirLT-Medium → Avenir-Medium）
+ (UIFont *)subtitleFontOfSize:(CGFloat)size;

#pragma mark - 字号（双稿 design 值）

+ (CGFloat)titleFontSizePhone;    // 28
+ (CGFloat)titleFontSizeIpad;     // 36
+ (CGFloat)subtitleFontSizePhone; // 22
+ (CGFloat)subtitleFontSizeIpad;  // 30

#pragma mark - 行高（双稿 design 值）

+ (CGFloat)titleLineHeightPhone;    // 34
+ (CGFloat)titleLineHeightIpad;     // 43
+ (CGFloat)subtitleLineHeightPhone; // 26
+ (CGFloat)subtitleLineHeightIpad;  // 36

#pragma mark - 间距（双稿 design 值）

/// 标题→副标题间距
+ (CGFloat)titleToSubtitleGapPhone; // 12
+ (CGFloat)titleToSubtitleGapIpad;  // 14

#pragma mark - 标题字距（负，双稿值）

+ (CGFloat)titleLetterSpacingPhone; // -0.48
+ (CGFloat)titleLetterSpacingIpad;  // -0.62

#pragma mark - 文字组的纵向位置（第一层子视图，按页面高度比例闭合）

/// 文字组 centerY / 页面高。**第一层子视图的纵向位置按页面高度比例闭合**（`proportional`）——
/// 不跟宽度档走，也不是「居中再挪一个常量」。
///
/// 稿件实测（`dds_layout` 绝对行盒）：
///   欢迎语           组 (27,320,339,72) → centerY 356 / 852  = 0.417840
///   启屏欢迎语-iPad  组 (187,377,436,93) → centerY 423.5/1080 = 0.392130
/// 旧代码写的是 `centerY == view.centerY + (-40)`，两稿都不对：
/// 真值是 −70（手机）与 −116.5（iPad）。
+ (CGFloat)textGroupCenterYRatioPhone;
+ (CGFloat)textGroupCenterYRatioIpad;

@end

NS_ASSUME_NONNULL_END
