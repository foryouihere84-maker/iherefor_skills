//
//  STSubscriptionRulesTests.m
//  SubTracker
//

#import <XCTest/XCTest.h>
#import "STSubscriptionRules.h"
#import "STSubscription.h"

@interface STSubscriptionRulesTests : XCTestCase

@end

@implementation STSubscriptionRulesTests

#pragma mark - 帮助方法

- (NSDate *)dateFromString:(NSString *)str {
    NSDateFormatter *fmt = [[NSDateFormatter alloc] init];
    fmt.dateFormat = @"yyyy-MM-dd";
    fmt.timeZone = [NSTimeZone timeZoneForSecondsFromGMT:0];
    fmt.locale = [NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];
    return [fmt dateFromString:str];
}

#pragma mark - dueDate（切片 1）

- (void)testDueDateMonthlyClampsToEndOfMonth {
    // 1/31 加 1 个月 → 2/28（裁剪，不是进位）
    NSDate *anchor = [self dateFromString:@"2023-01-31"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleMonthly
                                               occurrence:1
                                                    error:nil];
    XCTAssertEqualObjects(result, [self dateFromString:@"2023-02-28"]);
}

- (void)testDueDateMonthlyLeapYearClamps {
    // 2024 是闰年：1/31 → 2/29
    NSDate *anchor = [self dateFromString:@"2024-01-31"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleMonthly
                                               occurrence:1
                                                    error:nil];
    XCTAssertEqualObjects(result, [self dateFromString:@"2024-02-29"]);
}

- (void)testDueDateAnchorSingleStepDoesNotDrift {
    // 链式递推 1/31 +1M +1M = 3/28（漂移）；锚点单步 +2M 应 = 3/31
    NSDate *anchor = [self dateFromString:@"2023-01-31"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleMonthly
                                               occurrence:2
                                                    error:nil];
    XCTAssertEqualObjects(result, [self dateFromString:@"2023-03-31"],
                          @"锚点单步递推不得像链式那样漂移到 3/28");
}

- (void)testDueDateYearlyClampsLeapDay {
    // 2024-02-29 加 1 年 → 2025-02-28
    NSDate *anchor = [self dateFromString:@"2024-02-29"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleYearly
                                               occurrence:1
                                                    error:nil];
    XCTAssertEqualObjects(result, [self dateFromString:@"2025-02-28"]);
}

- (void)testDueDateWeeklyAdvances {
    NSDate *anchor = [self dateFromString:@"2023-01-02"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleWeekly
                                               occurrence:1
                                                    error:nil];
    XCTAssertEqualObjects(result, [self dateFromString:@"2023-01-09"]);
}

- (void)testDueDateOccurrenceZeroReturnsAnchor {
    NSDate *anchor = [self dateFromString:@"2023-01-31"];
    NSDate *result = [STSubscriptionRules dueDateForAnchor:anchor
                                                    cycle:STBillingCycleMonthly
                                               occurrence:0
                                                    error:nil];
    XCTAssertEqualObjects(result, anchor);
}

- (void)testDueDateNegativeOccurrenceErrors {
    NSError *error = nil;
    NSDate *result = [STSubscriptionRules dueDateForAnchor:[self dateFromString:@"2023-01-31"]
                                                    cycle:STBillingCycleMonthly
                                               occurrence:-1
                                                    error:&error];
    XCTAssertNil(result);
    XCTAssertEqual(error.code, STDomainErrorInvalidPeriod);
}

#pragma mark - evaluate（切片 2）

- (STSubscription *)makeSubWithTrialEndsAt:(NSDate *)trialEndsAt canceledAt:(NSDate *)canceledAt {
    return [[STSubscription alloc] initWithName:@"Netflix"
                                     priceCents:1999
                                          cycle:STBillingCycleMonthly
                                      startedAt:[self dateFromString:@"2023-01-31"]
                                    trialEndsAt:trialEndsAt
                                     canceledAt:canceledAt];
}

- (void)testEvaluateTrialStatusWhenTrialNotEnded {
    STSubscription *s = [self makeSubWithTrialEndsAt:[self dateFromString:@"2099-01-01"] canceledAt:nil];
    NSDate *asOf = [self dateFromString:@"2023-01-15"];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:asOf];
    XCTAssertEqual(snap.status, STSubscriptionStatusTrial);
}

- (void)testEvaluateActiveStatusAfterTrialEnded {
    STSubscription *s = [self makeSubWithTrialEndsAt:[self dateFromString:@"2023-01-10"] canceledAt:nil];
    NSDate *asOf = [self dateFromString:@"2023-01-15"];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:asOf];
    XCTAssertEqual(snap.status, STSubscriptionStatusActive);
}

- (void)testEvaluateCanceledOverridesTrial {
    // 即使还在试用期内，已取消的订阅状态应为 canceled（优先级：canceled > trial）
    STSubscription *s = [self makeSubWithTrialEndsAt:[self dateFromString:@"2099-01-01"] canceledAt:[self dateFromString:@"2023-01-05"]];
    NSDate *asOf = [self dateFromString:@"2023-01-15"];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:asOf];
    XCTAssertEqual(snap.status, STSubscriptionStatusCanceled);
}

- (void)testEvaluateNextBillingDateStrictlyAfterAsOf {
    // startedAt=2023-01-31 月度，asOf=2023-02-10 → 下一个严格晚于 asOf 的期次是 2/28
    STSubscription *s = [self makeSubWithTrialEndsAt:nil canceledAt:nil];
    NSDate *asOf = [self dateFromString:@"2023-02-10"];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:asOf];
    XCTAssertEqualObjects(snap.nextBillingDate, [self dateFromString:@"2023-02-28"]);
}

- (void)testEvaluateMonthlyCentsForMonthlyCycle {
    STSubscription *s = [self makeSubWithTrialEndsAt:nil canceledAt:nil];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s
                                                                       asOf:[self dateFromString:@"2023-01-15"]];
    // 月度 ×1 = 1999 分
    XCTAssertEqual(snap.monthlyCents, 1999);
}

- (void)testEvaluateTrialDaysLeft {
    STSubscription *s = [self makeSubWithTrialEndsAt:[self dateFromString:@"2023-01-20"] canceledAt:nil];
    NSDate *asOf = [self dateFromString:@"2023-01-15"];
    STSubscriptionSnapshot *snap = [STSubscriptionRules evaluateSubscription:s asOf:asOf];
    XCTAssertEqual(snap.trialDaysLeft, 5);
}

#pragma mark - summarize（切片 3）

- (void)testSummarizeMonthlyTotal {
    // 两条月付：1999 + 500 = 2499 分
    STSubscription *a = [[STSubscription alloc] initWithName:@"Netflix" priceCents:1999 cycle:STBillingCycleMonthly startedAt:[self dateFromString:@"2023-01-01"] trialEndsAt:nil canceledAt:nil];
    STSubscription *b = [[STSubscription alloc] initWithName:@"Spotify" priceCents:500 cycle:STBillingCycleMonthly startedAt:[self dateFromString:@"2023-01-01"] trialEndsAt:nil canceledAt:nil];
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:@[a, b] asOf:[self dateFromString:@"2023-01-15"] trialHorizonDays:7];
    XCTAssertEqual(sum.monthlyTotalCents, 2499);
}

- (void)testSummarizeYearlyDividesBy12 {
    // 年付 12000 分 → 月均 1000 分
    STSubscription *a = [[STSubscription alloc] initWithName:@"iCloud" priceCents:12000 cycle:STBillingCycleYearly startedAt:[self dateFromString:@"2023-01-01"] trialEndsAt:nil canceledAt:nil];
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:@[a] asOf:[self dateFromString:@"2023-01-15"] trialHorizonDays:7];
    XCTAssertEqual(sum.monthlyTotalCents, 1000);
}

- (void)testSummarizeTrialEndingSoonFiltersTrialWithinHorizon {
    // 试用 3 天后到期（在 7 天窗口内）→ 进入 trialEndingSoon
    STSubscription *a = [[STSubscription alloc] initWithName:@"Netflix" priceCents:1999 cycle:STBillingCycleMonthly startedAt:[self dateFromString:@"2023-01-01"] trialEndsAt:[self dateFromString:@"2023-01-18"] canceledAt:nil];
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:@[a] asOf:[self dateFromString:@"2023-01-15"] trialHorizonDays:7];
    XCTAssertEqual(sum.trialEndingSoon.count, 1);
}

- (void)testSummarizeExcludesCanceledFromTotal {
    // 已取消的订阅不计入月总支出
    STSubscription *a = [[STSubscription alloc] initWithName:@"Netflix" priceCents:1999 cycle:STBillingCycleMonthly startedAt:[self dateFromString:@"2023-01-01"] trialEndsAt:nil canceledAt:[self dateFromString:@"2023-01-10"]];
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:@[a] asOf:[self dateFromString:@"2023-01-15"] trialHorizonDays:7];
    XCTAssertEqual(sum.monthlyTotalCents, 0);
}

- (void)testSummarizeEmptyListIsZero {
    STLedgerSummary *sum = [STSubscriptionRules summarizeSubscriptions:@[] asOf:[self dateFromString:@"2023-01-15"] trialHorizonDays:7];
    XCTAssertEqual(sum.monthlyTotalCents, 0);
    XCTAssertEqual(sum.snapshots.count, 0);
}

@end
