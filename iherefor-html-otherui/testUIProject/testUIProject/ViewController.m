//
//  ViewController.m
//  testUIProject
//
//  项目管理入口：用一个列表枚举工程里所有的 ViewController，
//  点击任意一行即 push 到对应的视图，方便逐页联调与回归。
//

#import "ViewController.h"

#import "AgeSelectionViewController.h"
#import "BrushSelectionViewController.h"
#import "PaletteSelectionViewController.h"
#import "PurposeSelectionViewController.h"
#import "SpecialOfferViewController.h"
#import "StyleSelectionViewController.h"
#import "SubscriptionPlanSelectionViewController.h"

// 每个条目声明「列表上的名字」与「要创建哪个类」。
// 类用 NSString 表示并延迟创建，避免一次性初始化所有页面带来的副作用。
static NSArray<NSArray<NSString *> *> *s_Entries(void) {
    static NSArray<NSArray<NSString *> *> *entries;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        entries = @[
            @[ @"Age Selection",      @"AgeSelectionViewController" ],
            @[ @"Brush Selection",    @"BrushSelectionViewController" ],
            @[ @"Palette Selection",  @"PaletteSelectionViewController" ],
            @[ @"Purpose Selection",  @"PurposeSelectionViewController" ],
            @[ @"Special Offer",      @"SpecialOfferViewController" ],
            @[ @"Style Selection",    @"StyleSelectionViewController" ],
            @[ @"Subscription Plan",  @"SubscriptionPlanSelectionViewController" ],
        ];
    });
    return entries;
}

@interface ViewController () <UITableViewDataSource, UITableViewDelegate>
@end

@implementation ViewController {
    UITableView *_tableView;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"View Controllers";
    self.view.backgroundColor = [UIColor systemBackgroundColor];

    _tableView = [[UITableView alloc] initWithFrame:CGRectZero style:UITableViewStylePlain];
    _tableView.dataSource = self;
    _tableView.delegate = self;
    _tableView.rowHeight = UITableViewAutomaticDimension;
    _tableView.estimatedRowHeight = 48.0;
    [_tableView registerClass:[UITableViewCell class] forCellReuseIdentifier:@"Cell"];
    [self.view addSubview:_tableView];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    _tableView.frame = self.view.bounds;
}

#pragma mark - UITableViewDataSource

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    return (NSInteger)s_Entries().count;
}

- (UITableViewCell *)tableView:(UITableView *)tableView
         cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    UITableViewCell *cell = [tableView dequeueReusableCellWithIdentifier:@"Cell"
                                                           forIndexPath:indexPath];
    cell.textLabel.text = s_Entries()[(NSUInteger)indexPath.row][0];
    cell.accessoryType = UITableViewCellAccessoryDisclosureIndicator;
    return cell;
}

#pragma mark - UITableViewDelegate

- (void)tableView:(UITableView *)tableView didSelectRowAtIndexPath:(NSIndexPath *)indexPath {
    [tableView deselectRowAtIndexPath:indexPath animated:YES];

    NSString *className = s_Entries()[(NSUInteger)indexPath.row][1];
    Class cls = NSClassFromString(className);
    if (!cls || ![cls isSubclassOfClass:[UIViewController class]]) {
        NSLog(@"ViewController: unknown controller class %@", className);
        return;
    }

    UIViewController *controller = [[cls alloc] init];
    controller.title = s_Entries()[(NSUInteger)indexPath.row][0];
    [self.navigationController pushViewController:controller animated:YES];
}

@end
