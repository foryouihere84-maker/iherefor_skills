//
//  PaywallStyle.h
//  testUIProject
//
//  订阅付费墙（无免费试用）设计 token。整页样式恒量统一收敛于此，
//  字号 / 颜色 / 圆角 / 描边 / 字体族均取设计稿封闭值，不随屏幕缩放。
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface PaywallStyle : NSObject

#pragma mark - 颜色

/// 页面背景 #F1F0F2
+ (UIColor *)pageBackground;
/// 主标题 / 副标题文字 #161616
+ (UIColor *)titleColor;
/// 卡片文字（选中态深描边） #141414
+ (UIColor *)cardInk;
/// 卡片浅灰描边 #D7D7D7
+ (UIColor *)cardBorderMuted;
/// 卡片深描边（选中态） #141414
+ (UIColor *)cardBorderSelected;
/// CTA 与「Best Value」标签蓝紫 #5957FF
+ (UIColor *)accent;
/// 底部链接灰 #989795
+ (UIColor *)footerLink;
/// 关闭键圆形底填充 #D8D8D8（稿件 `rgba(216,216,216,1)`）。
/// 切图 `paywall_close_icon` 只含 ✕、**不含圆底**（32×32 透明画布，✕ 只占中间约 12×12），
/// 所以圆底要在代码里补 —— 不能指望资源图自带。
+ (UIColor *)closeButtonFill;
/// 关闭键圆形底描边 #979797（稿件 `rgba(151,151,151,1)`）。
+ (UIColor *)closeButtonBorder;

#pragma mark - 字体

/// 主标题字族（AvenirLT-Black → Avenir-Black）
+ (UIFont *)titleFont;
/// 副标题字族（AvenirLT-Medium → Avenir-Medium）
+ (UIFont *)subtitleFont;
/// 卡片标题字族（Avenir-Heavy）
+ (UIFont *)cardTitleFont;
/// 卡片副文本字族（Avenir-Medium）
+ (UIFont *)cardBodyFont;
/// 「Best Value」标签字族：稿件实测 size 10 / **Avenir-Heavy**——
/// 旧代码拿 `cardBodyFont`（Avenir-Medium）去画，字重与价格文字撞在一起，是错的。
+ (UIFont *)badgeFont;
/// CTA 文字字族（Avenir-Heavy）
+ (UIFont *)ctaFont;
/// 底部链接字族（Avenir-Medium）
+ (UIFont *)footerFont;

#pragma mark - 字体字号（设计值，不缩放）

+ (CGFloat)titleFontSize;      // 24
+ (CGFloat)subtitleFontSize;   // 15
+ (CGFloat)cardTitleFontSize;  // 16
+ (CGFloat)cardBodyFontSize;   // 10
+ (CGFloat)ctaFontSize;        // 20
+ (CGFloat)footerFontSize;     // 12

#pragma mark - 圆角与描边（设计值）

+ (CGFloat)cardCornerRadius;   // 16
+ (CGFloat)ctaCornerRadius;    // 34（胶囊）
+ (CGFloat)badgeCornerRadius;  // 6
+ (CGFloat)cardBorderWidth;    // 2

/// 关闭键圆形底描边宽度（设计常量，视觉值）：稿件 `borders[0].thickness = 2`，`position = 中心边框`。
/// 稿件矩形框 32×32 与描边圆半径重合，所以 `borderWidth` 2 + `cornerRadius = 高 ÷ 2` 即设计的两件套。
+ (CGFloat)closeButtonBorderWidth;  // 2

#pragma mark - 行高（设计值，走段落样式，不用高度约束）

/// 稿件 `font.line` 实测：标题 29（24pt）、副标题 18（15pt）、
/// 卡片标题 22（16pt）、卡片小字 14（10pt）、CTA 27（20pt）、底部链接 16（12pt）。
/// 这些比同字号的天然行高更紧，只能靠 `minimumLineHeight`/`maximumLineHeight` 压出来；
/// 给 label 钉一条高度约束会在大字号档把文字切掉，且把「行高」和「文本框高」混为一谈。
+ (CGFloat)titleLineHeight;      // 29
+ (CGFloat)subtitleLineHeight;  // 18
+ (CGFloat)cardTitleLineHeight; // 22
+ (CGFloat)cardBodyLineHeight;  // 14
+ (CGFloat)ctaLineHeight;       // 27
+ (CGFloat)footerLineHeight;    // 16

/// 价格与卡片小字的不透明度（设计常量）：稿件三处价格节点 `opacity = 60`。
+ (CGFloat)cardBodyAlpha;       // 0.6

#pragma mark - 几何（设计值；本页只有一份手机稿，跨宽度档不变）

/// 内容列封顶（**上限**，不是固定宽度）。声明判据：本页在设计列表里
/// **没有 `订阅-无免费试用-iPad` 稿**（项目 24 张稿中订阅只有一张），
/// 所以 iPad 侧没有任何独立出处，不能拿别处的数字冒充（skill §4.1：
/// 「只有一套稿时，平板上字大一点更好看」是错的）。
/// 480 因此是一个**判断值**：单列付费墙在宽屏上的可读上限，写明在这里以便复核。
/// 用 `<=` 而不是 `==` —— 写成固定 347/480 会在 iPad 分屏（~320pt）上直接溢出。
+ (CGFloat)maxContentWidth;        // 480

/// 内容列左右内边距（设计常量）：稿件 `col___85219` paddingLeft/Right = 23 → 393 − 46 = 347。
/// 宽度由「贴父 + 内边距 + 封顶」闭合，不再写 `equalToConstant`。
+ (CGFloat)contentHorizontalInset;  // 23

/// hero 高度（设计常量）。用 `fixed` 而不是 `aspect-ratio` 的依据：
/// 工程里两张 hero 切图的宽高比**互不相同**（`paywall_hero_top` 393×321 = 0.817、
/// `paywall_hero_top_ipad` 810×412 = 0.509），可见设计侧并不把 hero 高度当成宽度的函数；
/// 而本页没有 `xx-iPad` 稿作为第二出处，于是它只能是一个设计常量。
/// 表现：宽画布上 hero 仍是 321 高，图 `ScaleAspectFill` 是裁切而不是拉伸。
+ (CGFloat)heroHeight;              // 321

/// 价格卡高度（设计常量）：稿件 `row__882883_62074` / `row__442443_27483` 均为 68。
+ (CGFloat)cardHeight;              // 68

/// CTA 高度（设计常量）：稿件 `Block__66_4755` 高 68，胶囊（radius 34 = 68 ÷ 2）。
+ (CGFloat)ctaHeight;               // 68

@end

NS_ASSUME_NONNULL_END
