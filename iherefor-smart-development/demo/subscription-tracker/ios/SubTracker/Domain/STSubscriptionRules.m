//
//  STSubscriptionRules.m
//  SubTracker
//

#import "STSubscriptionRules.h"
#import "STSubscription.h"

NSErrorDomain const STDomainErrorDomain = @"STDomainErrorDomain";

@implementation STSubscriptionSnapshot

- (instancetype)initWithStatus:(STSubscriptionStatus)status
               nextBillingDate:(NSDate *)nextBillingDate
                  monthlyCents:(NSInteger)monthlyCents
                 trialDaysLeft:(NSInteger)trialDaysLeft {
    self = [super init];
    if (self) {
        _status = status;
        _nextBillingDate = nextBillingDate;
        _monthlyCents = monthlyCents;
        _trialDaysLeft = trialDaysLeft;
    }
    return self;
}

@end

@implementation STLedgerSummary

- (instancetype)initWithMonthlyTotalCents:(NSInteger)monthlyTotalCents
                                snapshots:(NSArray<STSubscriptionSnapshot *> *)snapshots
                          trialEndingSoon:(NSArray<STSubscriptionSnapshot *> *)trialEndingSoon {
    self = [super init];
    if (self) {
        _monthlyTotalCents = monthlyTotalCents;
        _snapshots = snapshots;
        _trialEndingSoon = trialEndingSoon;
    }
    return self;
}

@end

@implementation STSubscriptionRules

+ (NSDate *)dueDateForAnchor:(NSDate *)anchor
                       cycle:(STBillingCycle)cycle
                  occurrence:(NSInteger)occurrence
                       error:(NSError **)error {
    if (occurrence < 0) {
        if (error) {
            *error = [NSError errorWithDomain:STDomainErrorDomain
                                         code:STDomainErrorInvalidPeriod
                                     userInfo:nil];
        }
        return nil;
    }

    NSCalendar *calendar = [NSCalendar calendarWithIdentifier:NSCalendarIdentifierGregorian];
    NSDateComponents *components = [[NSDateComponents alloc] init];

    // 锚点单步递推：一次加 occurrence 个对应单位，绝不循环累加（防月末漂移）
    switch (cycle) {
        case STBillingCycleWeekly:
            components.day = occurrence * 7;
            break;
        case STBillingCycleMonthly:
            components.month = occurrence;
            break;
        case STBillingCycleYearly:
            components.year = occurrence;
            break;
    }

    return [calendar dateByAddingComponents:components toDate:anchor options:0];
}

+ (NSInteger)monthlyCentsForPriceCents:(NSInteger)priceCents cycle:(STBillingCycle)cycle {
    // 折月：weekly×52/12、monthly×1、yearly×1/12，HALF_UP 舍入到分（四舍五入）
    switch (cycle) {
        case STBillingCycleWeekly:
            return (NSInteger)lround((double)priceCents * 52.0 / 12.0);
        case STBillingCycleMonthly:
            return priceCents;
        case STBillingCycleYearly:
            return (NSInteger)lround((double)priceCents / 12.0);
    }
    return priceCents;
}

+ (STSubscriptionSnapshot *)evaluateSubscription:(STSubscription *)subscription
                                            asOf:(NSDate *)asOf {
    // 1. 求 nextBillingDate：从锚点递推，找第一个严格晚于 asOf 的期次
    NSInteger occurrence = 0;
    NSDate *nextBillingDate = nil;
    for (occurrence = 1; occurrence <= 1200; occurrence++) {
        NSDate *candidate = [self dueDateForAnchor:subscription.startedAt
                                             cycle:subscription.cycle
                                        occurrence:occurrence
                                             error:nil];
        if ([candidate compare:asOf] == NSOrderedDescending) {
            nextBillingDate = candidate;
            break;
        }
    }

    // 2. 状态判定：canceled > trial > (expired / active)
    STSubscriptionStatus status;
    if (subscription.canceledAt != nil) {
        status = STSubscriptionStatusCanceled;
    } else if (subscription.trialEndsAt != nil && [asOf compare:subscription.trialEndsAt] != NSOrderedDescending) {
        status = STSubscriptionStatusTrial;
    } else {
        // 简化：MVP 不追踪 canceledAt 已过导致的 expired，此处 active
        status = STSubscriptionStatusActive;
    }

    // 3. 折月金额
    NSInteger monthlyCents = [self monthlyCentsForPriceCents:subscription.priceCents cycle:subscription.cycle];

    // 4. 试用剩余天数（仅在 trial 状态有意义）
    NSInteger trialDaysLeft = -1;
    if (subscription.trialEndsAt != nil) {
        NSCalendar *cal = [NSCalendar calendarWithIdentifier:NSCalendarIdentifierGregorian];
        NSDate *start = [cal startOfDayForDate:asOf];
        NSDate *end = [cal startOfDayForDate:subscription.trialEndsAt];
        trialDaysLeft = [[cal components:NSCalendarUnitDay fromDate:start toDate:end options:0] day];
    }

    return [[STSubscriptionSnapshot alloc] initWithStatus:status
                                          nextBillingDate:nextBillingDate
                                             monthlyCents:monthlyCents
                                            trialDaysLeft:trialDaysLeft];
}

+ (STLedgerSummary *)summarizeSubscriptions:(NSArray<STSubscription *> *)subscriptions
                                       asOf:(NSDate *)asOf
                            trialHorizonDays:(NSInteger)trialHorizonDays {
    NSMutableArray<STSubscriptionSnapshot *> *snapshots = [NSMutableArray array];
    NSMutableArray<STSubscriptionSnapshot *> *trialEndingSoon = [NSMutableArray array];
    NSInteger total = 0;

    for (STSubscription *sub in subscriptions) {
        STSubscriptionSnapshot *snap = [self evaluateSubscription:sub asOf:asOf];
        [snapshots addObject:snap];

        // 只累加 active/trial（canceled/expired 不计入）
        if (snap.status == STSubscriptionStatusActive || snap.status == STSubscriptionStatusTrial) {
            total += snap.monthlyCents;
        }

        // 试用到期筛选：status=trial 且 0 ≤ trialDaysLeft ≤ horizon
        if (snap.status == STSubscriptionStatusTrial &&
            snap.trialDaysLeft >= 0 && snap.trialDaysLeft <= trialHorizonDays) {
            [trialEndingSoon addObject:snap];
        }
    }

    // 排序
    [snapshots sortUsingComparator:^NSComparisonResult(STSubscriptionSnapshot *a, STSubscriptionSnapshot *b) {
        return [a.nextBillingDate compare:b.nextBillingDate];
    }];
    [trialEndingSoon sortUsingComparator:^NSComparisonResult(STSubscriptionSnapshot *a, STSubscriptionSnapshot *b) {
        return [@(a.trialDaysLeft) compare:@(b.trialDaysLeft)];
    }];

    return [[STLedgerSummary alloc] initWithMonthlyTotalCents:total
                                                    snapshots:snapshots
                                              trialEndingSoon:trialEndingSoon];
}

@end
