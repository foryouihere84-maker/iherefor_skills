//
//  SplashStyle.h
//  testUIProject
//
//  启屏（启动页）设计 token。字号 / 颜色 / 尺寸取设计稿封闭值，不随屏幕缩放。
//  双稿（iPhone 393×852 / iPad 810×1080）各自取值，经 sizeVariants 分档。
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface SplashStyle : NSObject

#pragma mark - 颜色

/// 品牌文字颜色 rgba(20,20,20,1)
+ (UIColor *)brandTextColor;

/// 手机稿品牌文字投影颜色 rgba(86,116,255,0.16)。
///
/// 出处：`inspect_design_region` 对启屏品牌文字的实时回报 ——
/// `raw_style.shadow = [{ blurRadius: 0, offsetX: 0, offsetY: 2, color: rgba(86,116,255,0.16) }]`，
/// `dds_layout_suggestions.style.textShadow = "0px 2px 0px rgba(86,116,255,0.16)"`。
/// **注意**：缓存快照 `snapshot.json` 的 `nodes[].raw_style` 里没有 `shadows` 字段
/// （两稿都没有），所以这条值只能靠 MCP 实时查证 —— 不能因为快照里没有就当成臆造。
/// iPad 稿实时回报里**没有** `shadow` 键、`textShadow` 也缺省，即 iPad 无投影。
+ (UIColor *)brandTextShadowColor;

/// 品牌文字投影偏移（设计常量，视觉值，非比例）：手机稿实测 (0, 2)；iPad 稿无投影。
+ (CGSize)brandTextShadowOffset;

#pragma mark - 字体

/// 品牌文字字族（Futura-Medium，缺失时退化系统字体）
+ (UIFont *)brandFontOfSize:(CGFloat)size;

#pragma mark - 字号（双稿 design 值，不缩放）

/// 手机稿品牌文字字号
+ (CGFloat)brandFontSizePhone;
/// iPad 稿品牌文字字号
+ (CGFloat)brandFontSizeIpad;

#pragma mark - Logo 图标尺寸（双稿 design 值）

/// 手机稿 Logo 图标边长
+ (CGFloat)logoSizePhone;
/// iPad 稿 Logo 图标边长
+ (CGFloat)logoSizeIpad;

#pragma mark - Logo 到文字间距（双稿 design 值）

/// 手机稿图标→文字间距
+ (CGFloat)logoToTextGapPhone;
/// iPad 稿图标→文字间距
+ (CGFloat)logoToTextGapIpad;

#pragma mark - Logo 组的纵向位置（第一层子视图，按页面高度比例闭合）

/// Logo 组 centerY / 页面高。这是**第一层子视图的纵向位置按页面高度比例闭合**（`proportional`），
/// 不是「相对页面居中再挪一个常量」—— 两条轴都不共享同一个收口。
///
/// 稿件实测（`dds_layout` 绝对行盒）：
///   启屏      组 (140,280,114,146) → centerY 353 / 852  = 0.414319
///   启屏-iPad 组 (323,328,164,191) → centerY 423.5/1080 = 0.392130
/// 旧代码写的是 `centerY == view.centerY + (-40)`，对两稿都不成立：
/// 真值是 −73（手机）与 −116.5（iPad），量与比例都不是同一个东西。
+ (CGFloat)logoGroupCenterYRatioPhone;
+ (CGFloat)logoGroupCenterYRatioIpad;

@end

NS_ASSUME_NONNULL_END
