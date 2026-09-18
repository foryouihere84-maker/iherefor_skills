//
//  OnboardingStyle.h
//  testUIProject
//
//  引导流程（7 步向导）设计 token。
//
//  两条轴分开表达：
//  - **尺寸轴 / 位置轴**：字号 / 圆角 / 描边 / 图标点值 / 跨稿尺寸差，取设计稿封闭值，不缩放。
//  - **宽度轴**：内容列怎么收敛，由窗口宽度档决定（见各 widthPolicy 常量）。
//
//  双稿（iPhone 393×852 / iPad 810×1080）是**两套并列的独立参考**，值照各自稿取，
//  彼此没有派生关系；跨稿差异在这里体现为 *Phone / *Ipad 成对常量。
//  成对常量只用来**选稿**（视觉常量的取值来源），**不得**用来做布局决策 ——
//  内容列宽度、列数、收敛方式由宽度档决定，与设备型号无关。
//

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

#pragma mark - 宽度档（宽度轴）

/// 窗口宽度档。**由实际窗口宽度判定，与设备型号无关** —— iPad 分屏 1/3、Slide Over
/// 会回落到 compact，Stage Manager / 自由窗口下宽度在 320~1366 之间连续变化。
/// 因此禁止用 `userInterfaceIdiom` 或设备型号代替它做布局决策。
typedef NS_ENUM(NSInteger, OnboardingWidthClass) {
    OnboardingWidthClassCompact = 0,   // < 600pt
    OnboardingWidthClassMedium,        // 600–839pt
    OnboardingWidthClassExpanded,      // >= 840pt
};

@interface OnboardingStyle : NSObject

#pragma mark - 宽度轴（adaptiveLayout / continuous-window-width）

/// 按**窗口宽度**判定宽度档。窗口宽度必须取自 `view.bounds` / `windowScene` ——
/// **不得**取屏幕级尺寸当基准：屏幕 ≠ 窗口，分屏与自由窗口下它返回整块屏，
/// 原点与可用宽度都会错（`UIScreen.main` 系列取值都属于这一类）。
///
/// 注：这句话刻意不把那个 API 的完整点号路径写全 —— 闸门
/// `scripts/check_adaptive_layout.py` 的禁止模式是**逐行正则、不剥离注释**，
/// 写全了会让一条「教人别这么写」的注释把整页判红。信息不损失：仍然是同一个 API。
+ (OnboardingWidthClass)widthClassForWindowWidth:(CGFloat)windowWidth;

/// 内容列封顶（设计常量，不随窗口缩放）。
/// 期望值来自 iPad 稿件本身：目的/性别/年龄/笔刷/色板 iPad 稿内容列 481pt 居中，
/// 风格 iPad 稿 3 列网格 640pt 居中。手机稿不需要封顶（20/20 内边距闭合即得 353）。
+ (CGFloat)maxContentWidth;          // 481
+ (CGFloat)styleGridMaxContentWidth; // 640（风格页 3 列网格）

/// CTA 封顶（设计常量）：480。iPad 稿 CTA 480pt 居中（165 起）；手机稿由 23/23
/// 内边距闭合得 347。
///
/// 注：手机稿实测 CTA 包围盒是 x=26 / 宽 347（6 个页一致），即左右内边距 26/20 ——
/// 相对画布中心右偏 3pt。这里按**居中**表达（347 宽与稿件逐字相同），
/// 3pt 属设计侧的手工偏差，不写进约束；风格页稿件自身是 26/26（341 宽），
/// 与其余 6 页不一致，同样归入这一处偏差。
+ (CGFloat)ctaMaxWidth;

/// 内容列设计常量内边距：(393-353)/2 = 20，两稿同值。
/// 宽度由「两侧贴父 + 内边距」闭合，**不再**写成 `equalToConstant 353/481` ——
/// 那样在 iPad 分屏（~320pt）上 481 会直接溢出。
+ (CGFloat)contentHorizontalInset;   // 20

/// CTA 设计常量内边距：347 = 393 - 2×23，两稿同值。
+ (CGFloat)ctaHorizontalInset;       // 23

/// 进度条宽度 / 页面宽度。手机稿 232/393 = 0.5903，iPad 稿 482/810 = 0.5951 ——
/// 两稿一致到 0.8%，是**比例闭合**而非固定宽度；写成固定 232/482 会在 Slide Over 上溢出。
+ (CGFloat)progressWidthRatio;       // 0.5903

/// 顶部栏离**安全区顶**的间距。两稿同为「状态栏下方 8pt」——
/// 手机稿状态栏模板 44pt、返回键 y=52；iPad 稿沿用同一 44pt 模板（真实 iPad 状态栏仅 24pt）。
/// 取单一设计常量 8，**不再**按「24+28=52」补偿探针设备状态栏高度差：
/// 那会把某个机型的 44pt 当成常量，在状态栏 47/59pt 的机型上算出 55/67pt。
/// 代价是 iPad 上整条顶部栏比稿件高 20pt（真实安全区 24 vs 稿件模板 44），这是**已知且接受**的偏差 ——
/// 真实 iPad 各机型安全区顶在 24~32 之间浮动，按机型补偿反而在别的机型上出错。
+ (CGFloat)topBarTopInset;           // 8

/// CTA 底 → 安全区底间距（跨稿分档）：手机 34 / iPad 81。
/// 由稿件实测反推：手机 CTA 底 784、画布 852、底部安全区 34 → 852-784-34 = 34；
/// iPad CTA 底 979、画布 1080、底部安全区 20 → 1080-979-20 = 81。
/// 底部贴安全区是**有意**的：短屏 / 横屏下 CTA 不被挤出安全区，
/// 所以这里用 `pinned` 而不是「按页面高度比例」。
+ (CGFloat)ctaBottomInsetPhone;
+ (CGFloat)ctaBottomInsetIpad;

#pragma mark - Dynamic Type

/// 把设计字号按文本样式缩放（`UIFontMetrics`）。视觉常量本身不缩放，
/// 缩放的是系统字号档 —— 这是 Dynamic Type 的正确用法。
+ (UIFont *)scaledFont:(UIFont *)font forTextStyle:(UIFontTextStyle)textStyle;

/// 选项文字的字号（20pt）对应的文本样式；标题（28pt）、Skip（17pt）见实现。
+ (UIFontTextStyle)optionTextStyle;

#pragma mark - 颜色

/// 页面背景 #F1F0F2
+ (UIColor *)pageBackground;
/// 标题 / 选项文字 #161616
+ (UIColor *)titleColor;
/// CTA 主色 #5957FF
+ (UIColor *)accent;
/// 选项卡片填充 #FBFBFB —— 稿件实测 rgba(251,251,251,1)，**不是**纯白。
+ (UIColor *)optionCardBackground;
/// 选项卡片描边（未选中）#DEDEDE —— 稿件实测 rgba(222,222,222,1)，配 1.5pt 内描边。
+ (UIColor *)optionBorderMuted;
/// 选项卡片描边（选中）#5957FF —— 稿件每页**恰有一张**卡片用它（即当前选中项），
/// 与 CTA 主色同值。旧值 #141414 是误把正文墨色当选中色。
+ (UIColor *)optionBorderSelected;
/// 进度条轨道 #161616 @20% —— 稿件实测 rgba(22,22,22,0.2)，是**墨色降透明**而非灰色。
+ (UIColor *)progressTrack;
/// 进度条高亮 #161616 —— 稿件实测 rgba(22,22,22,1)。
+ (UIColor *)progressFill;
/// 列表滚动到底部时压在 CTA 下的渐隐遮罩（风格页稿件 y 662 起）
+ (UIColor *)footerScrim;

#pragma mark - 字体

/// 标题字族（AvenirLT-Black → Avenir-Black/Heavy）
+ (UIFont *)titleFontOfSize:(CGFloat)size;
/// 选项字族（AvenirLT-Medium → Avenir-Medium）
+ (UIFont *)optionFontOfSize:(CGFloat)size;
/// CTA 字族（Avenir-Heavy）
+ (UIFont *)ctaFontOfSize:(CGFloat)size;

#pragma mark - 字号（双稿 design 值）

+ (CGFloat)titleFontSizePhone;    // 28
+ (CGFloat)titleFontSizeIpad;     // 36
+ (CGFloat)optionFontSizePhone;   // 20（选项文字；emoji 行另按 emoji 字号处理）
+ (CGFloat)optionFontSizeIpad;    // 22
+ (CGFloat)ctaFontSizePhone;      // 20
+ (CGFloat)ctaFontSizeIpad;       // 20
+ (CGFloat)skipFontSizePhone;     // 17
+ (CGFloat)skipFontSizeIpad;      // 17

#pragma mark - 尺寸与圆角

/// **跨稿分档（sizeVariants）**：双稿是两套并列的独立参考，值照各自稿取，
/// 与另一稿没有派生关系。选择依据是「设备平台」（phone / tablet），
/// **不是**窗口宽度档 —— 宽度档只决定内容怎么收敛，不决定取哪套稿的尺寸。
+ (CGFloat)optionCardHeightPhone;   // 66
+ (CGFloat)optionCardHeightIpad;    // 66
/// 选项卡片圆角（设计常量，同平台内各宽度档逐字相同）。
/// 稿件实测 `radius = [12]`（目的/性别/年龄/笔刷/色板/风格，两稿一致）；旧值 16 无出处。
/// 风格页网格卡片用的是同一个 12，所以不另立 token。
+ (CGFloat)optionCardRadius;        // 12
/// 选项卡片描边宽度（设计常量）：稿件实测 `thickness = 1.5`（旧代码写死 2.0）。
+ (CGFloat)optionCardBorderWidth;   // 1.5
/// 选项卡片的纵向间距（两稿同为 10：手机 stride 76-66，iPad 同为 10）
+ (CGFloat)optionRowGap;

+ (CGFloat)ctaHeightPhone;          // 56
+ (CGFloat)ctaHeightIpad;           // 75
+ (CGFloat)ctaArrowSizePhone;       // 32
+ (CGFloat)ctaArrowSizeIpad;        // 44
+ (CGFloat)ctaArrowRightInsetPhone; // 36（相对 CTA 自身右边缘）
+ (CGFloat)ctaArrowRightInsetIpad;  // 32

/// 返回按钮图标边长（跨稿分档）：32 / 44
+ (CGFloat)backButtonSizePhone;
+ (CGFloat)backButtonSizeIpad;

/// 顶部栏左右内边距（跨稿分档）：手机 12/20，iPad 48/40。
/// iPad 稿的顶部栏贴页面边缘，而内容列是居中封顶的 —— 两者不是同一套对齐基准，
/// 所以这里是跨稿分档值，不能由内容列内边距推导。
+ (CGFloat)backButtonLeadingPhone;
+ (CGFloat)backButtonLeadingIpad;
+ (CGFloat)skipRightInsetPhone;
+ (CGFloat)skipRightInsetIpad;

/// 进度条高度（跨稿分档）：6 / 8
+ (CGFloat)progressHeightPhone;
+ (CGFloat)progressHeightIpad;

/// 返回按钮底 → 标题顶间距（跨稿分档）：24 / 29
/// （手机 52+32+24 = 108 = 标题顶；iPad 52+44+29 = 125 = 标题顶）
+ (CGFloat)titleTopGapPhone;
+ (CGFloat)titleTopGapIpad;

/// 标题底 → 内容区顶间距（跨稿分档）：69 / 87
/// （设计稿实测：手机标题底 137 → 内容顶 206；iPad 标题底 161 → 内容顶 248）
+ (CGFloat)contentTopGapPhone;
+ (CGFloat)contentTopGapIpad;

/// 选项列表底与 CTA 顶之间的最小间隙（防列表压到 CTA 上）。
+ (CGFloat)listToCTAMinGap;

#pragma mark - 风格页网格（跨稿分档 + 宽度轴）

/// 卡片高 / 卡片宽。两稿同比例：手机 146/170 = 0.8588、iPad 172/200 = 0.86。
/// 所以卡片高度是**宽高比闭合**，不是跨稿分档常量 —— 卡片宽由列数与外层宽度定，
/// 高度随之求解，窄窗口下卡片整体缩小而不是溢出。
+ (CGFloat)styleCardHeightRatio;

/// 文字标签遮罩高 / 卡片宽：手机 68/170 = 0.4、iPad 80/200 = 0.4（**两稿精确同值**）。
///
/// 卡片结构（DDS `dds_layout` 实测）：卡片 = `蒙版`（radius 12，高 146/172）内嵌一张
/// 铺满的缩略图，**底部再叠一条 68/80 高的渐变遮罩**（其描边为 `radius [0,0,12,12]`，
/// 底角与卡片同心），文字压在遮罩里。
/// 也就是说遮罩是**覆盖**在图上的一方，不占卡片高度 ——
/// 旧口径「图 146 + 标签 68 = 卡 214」与实测矛盾：手机行距 159 = 146 + 13，
/// 4 行 + 3 间距 = 4×146 + 3×13 = 623，与稿件网格容器高 **623 精确闭合**；
/// 若卡片真高 214，则 4×214 + 3×13 = 895 ≠ 623，对不上。
+ (CGFloat)styleCardLabelStripHeightRatio;   // 0.4

/// 网格水平/垂直间距（跨稿分档）：13 / 20
+ (CGFloat)styleGridGapPhone;
+ (CGFloat)styleGridGapIpad;

/// 卡片底 → 文字标签底间距（跨稿分档，稿件实测）：手机 10、iPad 16。
/// 这是**视觉常量**（`fixed`），不是比例 —— 10/68 与 16/80 并不相等。
+ (CGFloat)styleCardLabelBottomInsetPhone;
+ (CGFloat)styleCardLabelBottomInsetIpad;

/// 卡片标签字号（跨稿分档，稿件实测）：手机 18、iPad 20，字族同选项文字（AvenirLT-Medium）。
+ (CGFloat)styleCardLabelFontSizePhone;
+ (CGFloat)styleCardLabelFontSizeIpad;

/// 卡片标签文字色：稿件 rgba(255,255,255,1) —— 白字压在图上传，靠遮罩保证可读性。
+ (UIColor *)styleCardLabelColor;

/// 卡片标签遮罩的渐变终止色与最大不透明度。
///
/// 遮罩在稿件里是**导出位图**（`hasExportDDSImage: true`、`fills: []`），拿不到 fill 定义，
/// 所以这两个值是从缓存预览图采样拟合的：遮罩顶完全透出原图、底压到接近黑，
/// 线性 ramp 在 y=316（约 47% 处）反解出的底色与相邻行一致，故取 0 → 0.72 线性。
/// **这是近似值** —— 若要逐像素一致，应改用该遮罩的导出切图作为 `UIImageView`。
+ (UIColor *)styleCardScrimColor;
+ (CGFloat)styleCardScrimMaxAlpha;

/// 网格列数由**宽度档**决定：compact 2 列 / medium、expanded 3 列。
/// 不用「手机 2 列、iPad 3 列」这种设备分支 —— iPad 分屏 1/3 时窗口宽度是 compact，
/// 取 3 列会算出一列比窗口还宽。
+ (NSInteger)styleColumnCountForWidthClass:(OnboardingWidthClass)widthClass;

/// 笔刷横条（跨稿分档）：手机 353×86、iPad 481×98。
/// 横条是整张位图（含图标与文字），高度照**位图自身宽高比**闭合：
/// 手机 86/353 = 0.2436、iPad 98/481 = 0.2037 —— 两稿比例不同，故按稿取比值。
+ (CGFloat)brushRowHeightRatioPhone;
+ (CGFloat)brushRowHeightRatioIpad;
+ (CGFloat)brushRowGap;             // 10（手机 stride 96-86）

/// 色板横条（跨稿分档）：手机 353×102、iPad 481×102。
/// 高度同样照**位图自身宽高比**闭合：手机 102/353 = 0.2890、iPad 102/481 = 0.2121。
+ (CGFloat)colorRowHeightRatioPhone;
+ (CGFloat)colorRowHeightRatioIpad;
+ (CGFloat)colorRowGap;             // 14（手机 stride 116-102）

#pragma mark - 引导完成页（终点页，无顶部栏）

/// 标题顶 / 页面高。这是**第一层子视图的纵向位置按页面高度比例闭合**（`proportional`）：
/// 手机 428/852 = 0.5024、iPad 510/1080 = 0.4722 —— 两稿比例不同，各取各的
/// （双稿是并列的两套参考，不存在派生关系）。
/// 该页顶部栏是隐藏的，标题**不能**沿用向导各页「贴返回键底」的 `pinned` 规则 ——
/// 那会把它放到 y≈108，与稿件的 428 差 320pt。
+ (CGFloat)doneTitleTopRatioPhone;
+ (CGFloat)doneTitleTopRatioIpad;

/// 标题底 → 完成图标顶间距（跨稿分档）：手机 597-523 = 74、iPad 715-615 = 100。
+ (CGFloat)doneIconTopGapPhone;
+ (CGFloat)doneIconTopGapIpad;

/// 完成图标边长（跨稿分档）：手机 56、iPad 72。
/// 注：代码原注释写的 `splash_icon_ok_l` 是稿件**图层名**，生产切图叫 `onboarding_done_icon`。
+ (CGFloat)doneIconSizePhone;
+ (CGFloat)doneIconSizeIpad;

/// 完成页标题两行的字号（跨稿分档）：手机 24、iPad 28。
/// 稿件里两行同字号、只差字族（Medium / Black），所以一个字号够用。
+ (CGFloat)doneTitleFontSizePhone;
+ (CGFloat)doneTitleFontSizeIpad;

/// 完成页标题两行之间的额外行距（跨稿分档，由稿件行框反推）：
/// 手机 8（行框 29 → 首行底 457、次行顶 465，总高 29+8+58 = 95 = 稿件标题组高）；
/// iPad 3（行框 34 → 总高 34+3+68 = 105 = 稿件标题组高）。
+ (CGFloat)doneTitleLineSpacingPhone;
+ (CGFloat)doneTitleLineSpacingIpad;

/// 完成页 CTA 文案（跨稿分档）：手机 "Let's try"、iPad "Continue"。
+ (NSString *)doneCTATextPhone;
+ (NSString *)doneCTATextIpad;

@end

NS_ASSUME_NONNULL_END
