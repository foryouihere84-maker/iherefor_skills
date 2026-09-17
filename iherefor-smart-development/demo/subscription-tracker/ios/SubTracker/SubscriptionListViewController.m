//
//  SubscriptionListViewController.m
//  SubTracker
//

#import "SubscriptionListViewController.h"
#import "STSubscription.h"
#import "STSubscriptionRules.h"
#import "InMemorySubscriptionRepository.h"

@interface SubscriptionListViewController () <UITableViewDataSource, UITableViewDelegate>

@property (nonatomic, strong) InMemorySubscriptionRepository *repository;
@property (nonatomic, strong) NSMutableArray<STSubscription *> *subscriptions;
@property (nonatomic, strong) UITableView *tableView;
@property (nonatomic, strong) UIToolbar *summaryBar;
@property (nonatomic, strong) UILabel *summaryLabel;

@end

@implementation SubscriptionListViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"订阅";
    self.view.backgroundColor = [UIColor systemBackgroundColor];

    // 预置样例数据（验收用）
    [self loadSampleData];

    [self setupTableView];
    [self setupSummaryBar];
    [self setupAddButton];

    [self reloadData];
}

- (void)loadSampleData {
    NSCalendar *cal = [NSCalendar calendarWithIdentifier:NSCalendarIdentifierGregorian];
    NSDateFormatter *fmt = [[NSDateFormatter alloc] init];
    fmt.dateFormat = @"yyyy-MM-dd";
    fmt.timeZone = [NSTimeZone timeZoneForSecondsFromGMT:0];
    fmt.locale = [NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];

    STSubscription *netflix = [[STSubscription alloc] initWithName:@"Netflix"
                                                        priceCents:1999
                                                             cycle:STBillingCycleMonthly
                                                         startedAt:[fmt dateFromString:@"2026-09-01"]
                                                       trialEndsAt:nil
                                                        canceledAt:nil];
    STSubscription *spotify = [[STSubscription alloc] initWithName:@"Spotify"
                                                        priceCents:500
                                                             cycle:STBillingCycleMonthly
                                                         startedAt:[fmt dateFromString:@"2026-09-01"]
                                                       trialEndsAt:[fmt dateFromString:@"2026-09-20"]
                                                        canceledAt:nil];
    STSubscription *icloud = [[STSubscription alloc] initWithName:@"iCloud+"
                                                       priceCents:12000
                                                            cycle:STBillingCycleYearly
                                                        startedAt:[fmt dateFromString:@"2026-03-01"]
                                                      trialEndsAt:nil
                                                       canceledAt:nil];
    STSubscription *gym = [[STSubscription alloc] initWithName:@"健身年卡"
                                                    priceCents:6000
                                                         cycle:STBillingCycleYearly
                                                     startedAt:[fmt dateFromString:@"2026-06-15"]
                                                   trialEndsAt:nil
                                                    canceledAt:[fmt dateFromString:@"2026-09-01"]];

    self.subscriptions = [@[netflix, spotify, icloud, gym] mutableCopy];
    self.repository = [[InMemorySubscriptionRepository alloc] initWithSubscriptions:self.subscriptions];
}

- (void)setupTableView {
    self.tableView = [[UITableView alloc] initWithFrame:CGRectZero style:UITableViewStylePlain];
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    self.tableView.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:self.tableView];
}

- (void)setupSummaryBar {
    self.summaryBar = [[UIToolbar alloc] initWithFrame:CGRectZero];
    self.summaryBar.translatesAutoresizingMaskIntoConstraints = NO;
    self.summaryLabel = [[UILabel alloc] init];
    self.summaryLabel.font = [UIFont boldSystemFontOfSize:15];
    self.summaryLabel.textColor = [UIColor labelColor];
    self.summaryLabel.textAlignment = NSTextAlignmentCenter;
    UIBarButtonItem *item = [[UIBarButtonItem alloc] initWithCustomView:self.summaryLabel];
    self.summaryBar.items = @[item];
    [self.view addSubview:self.summaryBar];
}

- (void)setupAddButton {
    UIBarButtonItem *add = [[UIBarButtonItem alloc] initWithBarButtonSystemItem:UIBarButtonSystemItemAdd
                                                                          target:self
                                                                          action:@selector(addTapped)];
    self.navigationItem.rightBarButtonItem = add;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    CGFloat safeTop = self.view.safeAreaInsets.top;
    self.summaryBar.frame = CGRectMake(0, safeTop, self.view.bounds.size.width, 44);
    CGFloat y = safeTop + 44;
    self.tableView.frame = CGRectMake(0, y, self.view.bounds.size.width, self.view.bounds.size.height - y);
}

- (void)reloadData {
    NSDate *now = [NSDate date];
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:self.subscriptions
                                                                  asOf:now
                                                       trialHorizonDays:7];
    self.summaryLabel.text = [NSString stringWithFormat:@"每月总支出：¥%.2f  ·  共 %lu 条", sum.monthlyTotalCents / 100.0, (unsigned long)self.subscriptions.count];
    [self.tableView reloadData];
}

- (void)addTapped {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"添加订阅"
                                                                   message:@"输入名称和月/年金额（分）"
                                                            preferredStyle:UIAlertControllerStyleAlert];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"名称";
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"金额（分）";
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addAction:[UIAlertAction actionWithTitle:@"取消" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"添加" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        NSString *name = alert.textFields[0].text ?: @"";
        NSInteger cents = [alert.textFields[1].text integerValue];
        if (name.length == 0 || cents <= 0) return;
        NSDate *today = [NSDate date];
        STSubscription *s = [[STSubscription alloc] initWithName:name
                                                      priceCents:cents
                                                           cycle:STBillingCycleMonthly
                                                       startedAt:today
                                                     trialEndsAt:nil
                                                      canceledAt:nil];
        [self.subscriptions addObject:s];
        [self reloadData];
    }]];
    [self presentViewController:alert animated:YES completion:nil];
}

#pragma mark - UITableViewDataSource

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    return self.subscriptions.count;
}

- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    static NSString *cid = @"cell";
    UITableViewCell *cell = [tableView dequeueReusableCellWithIdentifier:cid];
    if (!cell) {
        cell = [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:cid];
    }
    STSubscription *s = self.subscriptions[indexPath.row];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:[NSDate date]];
    NSDateFormatter *fmt = [[NSDateFormatter alloc] init];
    fmt.dateFormat = @"yyyy-MM-dd";
    fmt.timeZone = [NSTimeZone timeZoneForSecondsFromGMT:0];
    fmt.locale = [NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];

    NSString *statusText = @"";
    NSString *priceText = [NSString stringWithFormat:@"¥%.2f", snap.monthlyCents / 100.0];
    switch (snap.status) {
        case STSubscriptionStatusTrial: statusText = @" · 试用中"; break;
        case STSubscriptionStatusCanceled: statusText = @" · 已取消"; break;
        case STSubscriptionStatusActive: statusText = @""; break;
        case STSubscriptionStatusExpired: statusText = @" · 已过期"; break;
    }
    cell.textLabel.text = [NSString stringWithFormat:@"%@  %@%@", s.name, priceText, statusText];
    cell.detailTextLabel.text = [NSString stringWithFormat:@"下次扣款：%@", [fmt stringFromDate:snap.nextBillingDate]];
    return cell;
}

@end
