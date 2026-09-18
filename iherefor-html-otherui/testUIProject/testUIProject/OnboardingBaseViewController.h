//
//  OnboardingBaseViewController.h
//  testUIProject
//
//  引导流程骨架基类：顶部返回键 + 进度条 + Skip + 标题 + 可滚动选项区 + 底部 Continue CTA。
//  7 个引导步骤（目的/性别/年龄/风格/笔刷/色板/引导完成）继承它，各自重写选项区。
//
//  **两条轴的分工**（见 references/sizing-and-positioning.md、adaptive-layout.md）：
//
//  - 尺寸 / 位置：每个元素按「由谁闭合」表达。
//    内容列与 CTA 的宽度由 *贴安全区边的内边距* 闭合（`pinned`）+ 封顶（`bounded`）+ 居中（`centered`），
//    **不写** `equalToConstant 353/481`；进度条宽度按页面宽度比例闭合（`proportional`）；
//    背景装饰图高度按位图自身宽高比闭合（`aspect-ratio`）。
//  - 宽度轴：内容列怎么收敛，由**窗口宽度档**决定（`contentHorizontalInset` + `maxContentWidth`），
//    与设备型号无关。`usesTabletDesignValues` **只用于选稿**（取哪一套设计常量），
//    不参与任何布局决策。
//

#import <UIKit/UIKit.h>
#import "OnboardingStyle.h"

NS_ASSUME_NONNULL_BEGIN

@interface OnboardingBaseViewController : UIViewController

/// 引导标题文案（子类重写）
@property (nonatomic, copy, readonly) NSString *titleText;

/// 标题富文本（默认返回 nil，走 titleText + 单字体；完成页等多段字体的页重写）
- (NSAttributedString *)titleAttributedText;

/// 当前步骤索引（1 起）
@property (nonatomic, assign) NSUInteger stepIndex;
/// 总步骤数
@property (nonatomic, assign) NSUInteger totalSteps;

/// 选项区容器（子类往里加内容）。父视图是滚动容器的 contentLayoutGuide，
/// **不是** page —— 子类元素的位置基准是它（第二层，相对直接父视图固定）。
@property (nonatomic, strong, readonly) UIView *optionContainer;

/// 子类重写：构建选项区内容
- (void)buildOptions;

/// 是否选中了某个选项（启用 Continue）
@property (nonatomic, assign) BOOL hasSelection;
/// 选中的值（供子类记录，弱类型 id）
@property (nonatomic, strong, nullable) id selectedValue;

/// 隐藏顶部返回键与 Skip（引导完成等终点页设为 YES）
@property (nonatomic, assign) BOOL hidesBackAndSkip;

/// 选项列表滚到 CTA 底下时是否铺一层底部遮罩（风格页等长列表设为 YES）
@property (nonatomic, assign) BOOL showsFooterScrim;

/// Continue 点击（子类可重写跳转）
- (void)didTapContinue:(id)sender;
/// 返回（默认 pop）
- (void)didTapBack:(id)sender;
/// 跳过（默认进入最后一步）
- (void)didTapSkip:(id)sender;

#pragma mark - 宽度轴

/// 当前窗口宽度档。由 `view.bounds.size.width` 判定，`traitCollectionDidChange`
/// 时重算 —— iPad 分屏 1/3、Slide Over、Stage Manager 都会走到。
@property (nonatomic, assign, readonly) OnboardingWidthClass widthClass;

/// 宽度档变化时调用（`viewDidLoad` 末尾一次 + 之后每次档位变化）。
/// 子类重写以在档位切换时**重排**（例如风格页网格的列数由 2 变 3 需要重建行）。
/// 重写时必须先调 `super`。
- (void)applyWidthClass;

#pragma mark - 选稿（双稿是两套并列的独立参考）

/// 取哪一套设计常量：YES = `xx-iPad` 稿，NO = `xx` 稿。
/// **只用来选稿** —— 字号 / 圆角 / 图标点值 / 跨稿尺寸差。
/// 布局决策（内容列宽度、收敛方式、列数）一律走宽度档，**不得**读这个值。
///
/// 「设备平台」与「窗口宽度档」是**正交**的两维：前者回答「照哪套稿的尺寸/字号」，
/// 后者回答「父视图变宽时内容怎么收敛」（见 `scripts/audit_adaptive.py` 的分工说明）。
///
/// 这是选稿的**唯一来源**：基类自身的 token 与子类一样都实时读本方法，
/// 不另存一份缓存 —— 否则子类重写（例如某页只有手机稿、要强制取手机常量）时，
/// 基类那份缓存仍然停在默认实现的结果上，同一页会出现两套选稿结果。
- (BOOL)usesTabletDesignValues;

/// 标题标签（基类创建）。子类若要自己重排标题的纵向位置，需要读它。
@property (nonatomic, strong, readonly) UILabel *titleLabel;

/// 标题的**纵向闭口**约束，默认是「贴返回键底」（`pinned`，向导各页都是这个口径）。
///
/// 「内容居中」型页面（引导完成 —— 顶部栏隐藏、标题落在页面约一半处）重写本方法，
/// 返回按**页面高度比例**闭合的约束（`proportional`）：
/// `[self.titleLabel.topAnchor constraintEqualToAnchor:self.view.bottomAnchor multiplier:ratio]`。
///
/// 注意是**替换**而不是叠加：重写后基类不再装默认那条，所以不会留下一条永远打架的约束
/// （用优先级硬顶会留下，且不产生 broken constraint 日志，属于没症状的错法）。
- (NSLayoutConstraint *)titleTopConstraint;

#pragma mark - 子类可重写的尺寸与文案

/// 标题字号（双稿）
- (CGFloat)titleFontSize;
/// 内容列封顶（默认 `OnboardingStyle.maxContentWidth`；风格页 3 列网格重写为 640）
- (CGFloat)maxContentWidth;
/// 单行选项卡高度（双稿）
- (CGFloat)optionCardHeight;
/// CTA 高度（双稿）
- (CGFloat)ctaHeight;
/// CTA 文案
- (NSString *)ctaText;
/// 下一步要 push 的 VC 类（子类重写；返回 Nil 表示无下一步）
- (Class)nextViewControllerClass;

@end

NS_ASSUME_NONNULL_END
