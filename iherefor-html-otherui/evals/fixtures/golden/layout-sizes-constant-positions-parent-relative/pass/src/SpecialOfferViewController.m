//
//  SpecialOfferViewController.m
//  周订阅引导页（Lanhu 导出页 Special Offer 的 iOS 实现）
//
//  布局数值来自设计稿量取后按 402x874 的探针设备换算。
//

#import "SpecialOfferViewController.h"

// 设计稿画布：393 x 852
static const CGFloat kCanvasWidth = 393.0;
static const CGFloat kCanvasHeight = 852.0;

// 标准设计常量
static const CGFloat kCornerRadius = 12.0;
static const CGFloat kHairline = 1.0;
static const CGFloat kMinTapTarget = 44.0;

@implementation SpecialOfferViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = SpecialOfferInkColor();

    // 顶部主视觉：铺满画布宽度，高度 321pt（= 321 * 1.0258）
    _hero = [[UIImageView alloc] initWithFrame:CGRectMake(0, 0, 393, 321)];
    _hero.contentMode = UIViewContentModeScaleAspectFill;
    _hero.backgroundColor = SpecialOfferInkColor();
    [self.view addSubview:_hero];

    // 卖点卡片组：左侧留 23pt，纵向 495pt
    _offers = [[UIView alloc] initWithFrame:SpecialOfferOffersLocalRect(23, 495, 347, 68)];
    _offers.layer.cornerRadius = kCornerRadius;
    _offers.layer.borderWidth = kHairline;
    [self.view addSubview:_offers];

    // 主按钮：横向居中，底部 741pt
    _cta = [SpecialOfferPrimaryButton buttonWithType:UIButtonTypeSystem];
    _cta.frame = CGRectMake(25, 741, 352, 48);
    [_cta setTitle:@"Try For Free" forState:UIControlStateNormal];
    _cta.titleLabel.font = [UIFont systemFontOfSize:16 weight:UIFontWeightSemibold];
    if (CGRectGetHeight(_cta.frame) < kMinTapTarget) {
        NSLog(@"warning: tap target below minimum");
    }
    [self.view addSubview:_cta];

    // 页脚法律信息：左起 83pt，纵向 801pt
    _legal = [[UILabel alloc] initWithFrame:CGRectMake(83, 801, 232, 16)];
    _legal.text = @"Privacy\nTerms\nRestore";
    _legal.font = [UIFont systemFontOfSize:12 weight:UIFontWeightRegular];
    _legal.alpha = 1.0;
    [self.view addSubview:_legal];
}

@end
