//
//  OnboardingStyle.m
//  testUIProject
//
//  引导流程设计 token 实现。
//

#import "OnboardingStyle.h"

@implementation OnboardingStyle

#pragma mark - 宽度轴（adaptiveLayout / continuous-window-width）

// 与 check_adaptive_layout.py 的 WIDTH_CLASS_RANGES 同口径：
// compact (0,600) / medium (600,840) / expanded (840, inf)
+ (OnboardingWidthClass)widthClassForWindowWidth:(CGFloat)windowWidth {
    if (windowWidth < 600.0) { return OnboardingWidthClassCompact; }
    if (windowWidth < 840.0) { return OnboardingWidthClassMedium; }
    return OnboardingWidthClassExpanded;
}

+ (CGFloat)maxContentWidth          { return 481.0; }
+ (CGFloat)styleGridMaxContentWidth { return 640.0; }
+ (CGFloat)ctaMaxWidth              { return 480.0; }
+ (CGFloat)contentHorizontalInset   { return 20.0; }
+ (CGFloat)ctaHorizontalInset       { return 23.0; }

// 手机稿 232/393 = 0.5903，iPad 稿 482/810 = 0.5951，取手机稿（差 0.8%，视觉不可辨）。
+ (CGFloat)progressWidthRatio { return 232.0 / 393.0; }

+ (CGFloat)topBarTopInset { return 8.0; }

+ (CGFloat)ctaBottomInsetPhone { return 34.0; }
+ (CGFloat)ctaBottomInsetIpad  { return 81.0; }

#pragma mark - Dynamic Type

+ (UIFont *)scaledFont:(UIFont *)font forTextStyle:(UIFontTextStyle)textStyle {
    return [[UIFontMetrics metricsForTextStyle:textStyle] scaledFontForFont:font];
}

+ (UIFontTextStyle)optionTextStyle { return UIFontTextStyleTitle3; }   // 20pt

#pragma mark - 颜色

+ (UIColor *)pageBackground    { return [UIColor colorWithRed:241/255.0 green:240/255.0 blue:242/255.0 alpha:1.0]; }
+ (UIColor *)titleColor        { return [UIColor colorWithRed:22/255.0 green:22/255.0 blue:22/255.0 alpha:1.0]; }
+ (UIColor *)accent            { return [UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1.0]; }
// 卡片填充：稿件 rgba(251,251,251,1)。旧代码用 whiteColor（#FFFFFF），差 4/255。
+ (UIColor *)optionCardBackground { return [UIColor colorWithRed:251/255.0 green:251/255.0 blue:251/255.0 alpha:1.0]; }
// 未选中描边：稿件 rgba(222,222,222,1)。旧值 #D7D7D7 偏深 7/255。
+ (UIColor *)optionBorderMuted { return [UIColor colorWithRed:222/255.0 green:222/255.0 blue:222/255.0 alpha:1.0]; }
// 选中描边：稿件 rgba(89,87,255,1) —— 与 accent 同值，不是墨色。
+ (UIColor *)optionBorderSelected { return [UIColor colorWithRed:89/255.0 green:87/255.0 blue:255/255.0 alpha:1.0]; }
// 进度条轨道：稿件 rgba(22,22,22,0.2) —— 墨色降透明，不是灰。
+ (UIColor *)progressTrack     { return [UIColor colorWithRed:22/255.0 green:22/255.0 blue:22/255.0 alpha:0.2]; }
// 进度条高亮：稿件 rgba(22,22,22,1)。
+ (UIColor *)progressFill      { return [UIColor colorWithRed:22/255.0 green:22/255.0 blue:22/255.0 alpha:1.0]; }
+ (UIColor *)footerScrim       { return [UIColor colorWithWhite:1.0 alpha:0.92]; }

#pragma mark - 字体

+ (UIFont *)titleFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Avenir-Black" size:size];
    if (!f) { f = [UIFont fontWithName:@"Avenir-Heavy" size:size]; }
    if (!f) { f = [UIFont systemFontOfSize:size weight:UIFontWeightHeavy]; }
    return f;
}

+ (UIFont *)optionFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Avenir-Medium" size:size];
    if (!f) { f = [UIFont systemFontOfSize:size weight:UIFontWeightMedium]; }
    return f;
}

+ (UIFont *)ctaFontOfSize:(CGFloat)size {
    UIFont *f = [UIFont fontWithName:@"Avenir-Heavy" size:size];
    if (!f) { f = [UIFont systemFontOfSize:size weight:UIFontWeightHeavy]; }
    return f;
}

#pragma mark - 字号（双稿 design 值）

+ (CGFloat)titleFontSizePhone  { return 28.0; }
+ (CGFloat)titleFontSizeIpad   { return 36.0; }
+ (CGFloat)optionFontSizePhone { return 20.0; }
+ (CGFloat)optionFontSizeIpad  { return 22.0; }
+ (CGFloat)ctaFontSizePhone    { return 20.0; }
+ (CGFloat)ctaFontSizeIpad     { return 20.0; }
+ (CGFloat)skipFontSizePhone   { return 17.0; }
+ (CGFloat)skipFontSizeIpad    { return 17.0; }

#pragma mark - 尺寸与圆角（双稿 design 值）

+ (CGFloat)optionCardHeightPhone { return 66.0; }
+ (CGFloat)optionCardHeightIpad  { return 66.0; }
// 稿件实测 radius 12（两稿一致）；旧值 16 无出处。
+ (CGFloat)optionCardRadius      { return 12.0; }
// 稿件实测 thickness 1.5；旧代码在 6 个子类里写死 2.0。
+ (CGFloat)optionCardBorderWidth { return 1.5; }
+ (CGFloat)optionRowGap          { return 10.0; }

+ (CGFloat)ctaHeightPhone        { return 56.0; }
+ (CGFloat)ctaHeightIpad         { return 75.0; }
+ (CGFloat)ctaArrowSizePhone     { return 32.0; }
+ (CGFloat)ctaArrowSizeIpad      { return 44.0; }
+ (CGFloat)ctaArrowRightInsetPhone { return 36.0; }
+ (CGFloat)ctaArrowRightInsetIpad  { return 32.0; }

+ (CGFloat)backButtonSizePhone   { return 32.0; }
+ (CGFloat)backButtonSizeIpad    { return 44.0; }
+ (CGFloat)backButtonLeadingPhone{ return 12.0; }
+ (CGFloat)backButtonLeadingIpad { return 48.0; }

// Skip 右边距：手机 20（Skip @346、画布 393）；iPad 40（Skip @731、画布 810）。
+ (CGFloat)skipRightInsetPhone   { return 20.0; }
+ (CGFloat)skipRightInsetIpad    { return 40.0; }

+ (CGFloat)progressHeightPhone   { return 6.0; }
+ (CGFloat)progressHeightIpad    { return 8.0; }

+ (CGFloat)titleTopGapPhone      { return 24.0; }
+ (CGFloat)titleTopGapIpad       { return 29.0; }

// 标题底 → 内容顶：手机 206-137 = 69；iPad 248-161 = 87。
+ (CGFloat)contentTopGapPhone    { return 69.0; }
+ (CGFloat)contentTopGapIpad     { return 87.0; }

+ (CGFloat)listToCTAMinGap       { return 16.0; }

#pragma mark - 风格页网格

// 卡片高 / 卡片宽：手机 146/170 = 0.8588，iPad 172/200 = 0.86。
+ (CGFloat)styleCardHeightRatio { return 146.0 / 170.0; }

// 标签遮罩高 / 卡片宽：手机 68/170 = 0.4，iPad 80/200 = 0.4（精确同值）。
// 遮罩是叠在缩略图底部的一层，不占卡片高度 —— 见头文件里的闭合验算。
+ (CGFloat)styleCardLabelStripHeightRatio { return 0.4; }

+ (CGFloat)styleGridGapPhone { return 13.0; }
+ (CGFloat)styleGridGapIpad  { return 20.0; }

// 卡片底 → 标签文字底：手机 10、iPad 16（稿件实测，不是比例）。
+ (CGFloat)styleCardLabelBottomInsetPhone { return 10.0; }
+ (CGFloat)styleCardLabelBottomInsetIpad  { return 16.0; }

// 卡片标签字号：手机 18、iPad 20（稿件实测）。
+ (CGFloat)styleCardLabelFontSizePhone { return 18.0; }
+ (CGFloat)styleCardLabelFontSizeIpad  { return 20.0; }

// 卡片标签白字 + 深色遮罩。遮罩在稿件里是导出位图，此处按预览图采样拟合为线性渐变。
+ (UIColor *)styleCardLabelColor  { return [UIColor whiteColor]; }
+ (UIColor *)styleCardScrimColor  { return [UIColor blackColor]; }
+ (CGFloat)styleCardScrimMaxAlpha { return 0.72; }

// 列数**不按设备**，按宽度档：compact 2 列 / medium、expanded 3 列。
+ (NSInteger)styleColumnCountForWidthClass:(OnboardingWidthClass)widthClass {
    return widthClass == OnboardingWidthClassCompact ? 2 : 3;
}

// 笔刷横条高 / 宽：手机 86/353 = 0.2436，iPad 98/481 = 0.2037（两稿比例不同）。
+ (CGFloat)brushRowHeightRatioPhone { return 86.0 / 353.0; }
+ (CGFloat)brushRowHeightRatioIpad  { return 98.0 / 481.0; }
+ (CGFloat)brushRowGap              { return 10.0; }

// 色板横条高 / 宽：手机 102/353 = 0.2890，iPad 102/481 = 0.2121。
+ (CGFloat)colorRowHeightRatioPhone { return 102.0 / 353.0; }
+ (CGFloat)colorRowHeightRatioIpad  { return 102.0 / 481.0; }
+ (CGFloat)colorRowGap              { return 14.0; }

#pragma mark - 引导完成页（终点页，无顶部栏）

// 标题顶 / 页面高：手机 428/852、iPad 510/1080。
+ (CGFloat)doneTitleTopRatioPhone { return 428.0 / 852.0; }
+ (CGFloat)doneTitleTopRatioIpad  { return 510.0 / 1080.0; }

// 标题底 → 图标顶：手机 74、iPad 100。
+ (CGFloat)doneIconTopGapPhone { return 74.0; }
+ (CGFloat)doneIconTopGapIpad  { return 100.0; }

// 完成图标边长：手机 56、iPad 72。
+ (CGFloat)doneIconSizePhone { return 56.0; }
+ (CGFloat)doneIconSizeIpad  { return 72.0; }

// 完成页标题字号：手机 24、iPad 28；两行额外行距 手机 8 / iPad 3。
+ (CGFloat)doneTitleFontSizePhone { return 24.0; }
+ (CGFloat)doneTitleFontSizeIpad  { return 28.0; }
+ (CGFloat)doneTitleLineSpacingPhone { return 8.0; }
+ (CGFloat)doneTitleLineSpacingIpad  { return 3.0; }

+ (NSString *)doneCTATextPhone { return @"Let\u2019s try"; }
+ (NSString *)doneCTATextIpad  { return @"Continue"; }

@end
