//
//  STSubscriptionRules.h
//  SubTracker
//

#import <Foundation/Foundation.h>
#import "STBillingCycle.h"
#import "STSubscriptionStatus.h"

@class STSubscription;

NS_ASSUME_NONNULL_BEGIN

/// 一条订阅在某个时刻的完整快照。
@interface STSubscriptionSnapshot : NSObject

@property (nonatomic, readonly) STSubscriptionStatus status;
@property (nonatomic, readonly, strong) NSDate *nextBillingDate;
@property (nonatomic, readonly) NSInteger monthlyCents;
@property (nonatomic, readonly) NSInteger trialDaysLeft; // 无试用时为 -1

- (instancetype)initWithStatus:(STSubscriptionStatus)status
               nextBillingDate:(NSDate *)nextBillingDate
                  monthlyCents:(NSInteger)monthlyCents
                 trialDaysLeft:(NSInteger)trialDaysLeft;

@end

/// 账单概览（summarize 的聚合结果）。
@interface STLedgerSummary : NSObject

@property (nonatomic, readonly) NSInteger monthlyTotalCents;
@property (nonatomic, readonly, strong) NSArray<STSubscriptionSnapshot *> *snapshots;
@property (nonatomic, readonly, strong) NSArray<STSubscriptionSnapshot *> *trialEndingSoon;

- (instancetype)initWithMonthlyTotalCents:(NSInteger)monthlyTotalCents
                                snapshots:(NSArray<STSubscriptionSnapshot *> *)snapshots
                          trialEndingSoon:(NSArray<STSubscriptionSnapshot *> *)trialEndingSoon;

@end

/// 领域层纯函数（共享层语义见 shared-layer.md），无状态、无 I/O、不读系统时钟。
@interface STSubscriptionRules : NSObject

/// 从锚点单步递推 occurrence 期的日期。occurrence=0 返回 anchor 本身。
/// 禁止链式累加（防月末漂移）；目标月无该日则裁到月末。
/// occurrence < 0 时 error 置为 STDomainErrorInvalidPeriod。
+ (nullable NSDate *)dueDateForAnchor:(NSDate *)anchor
                                cycle:(STBillingCycle)cycle
                           occurrence:(NSInteger)occurrence
                                error:(NSError *_Nullable *_Nullable)error;

/// 算出一条订阅在 asOf 时刻的完整快照（状态 + 下次扣款日 + 折月金额 + 试用剩余天数）。
+ (STSubscriptionSnapshot *)evaluateSubscription:(STSubscription *)subscription
                                            asOf:(NSDate *)asOf;

/// 把一组订阅汇总成账单概览。trialHorizonDays 默认 7（7 天内到期的试用进入 trialEndingSoon）。
+ (STLedgerSummary *)summarizeSubscriptions:(NSArray<STSubscription *> *)subscriptions
                                       asOf:(NSDate *)asOf
                            trialHorizonDays:(NSInteger)trialHorizonDays;

@end

FOUNDATION_EXPORT NSErrorDomain const STDomainErrorDomain;

typedef NS_ERROR_ENUM(STDomainErrorDomain, STDomainError) {
    STDomainErrorInvalidPeriod = 1,
    STDomainErrorInvalidPrice = 2,
    STDomainErrorInvalidHorizon = 3,
};

NS_ASSUME_NONNULL_END
