//
//  STSubscription.h
//  SubTracker
//

#import <Foundation/Foundation.h>
#import "STBillingCycle.h"

NS_ASSUME_NONNULL_BEGIN

@interface STSubscription : NSObject

@property (nonatomic, readonly, copy) NSString *name;
@property (nonatomic, readonly) NSInteger priceCents;
@property (nonatomic, readonly) STBillingCycle cycle;
@property (nonatomic, readonly, strong) NSDate *startedAt;
@property (nonatomic, readonly, strong, nullable) NSDate *trialEndsAt;
@property (nonatomic, readonly, strong, nullable) NSDate *canceledAt;

- (instancetype)initWithName:(NSString *)name
                  priceCents:(NSInteger)priceCents
                       cycle:(STBillingCycle)cycle
                   startedAt:(NSDate *)startedAt
                 trialEndsAt:(nullable NSDate *)trialEndsAt
                  canceledAt:(nullable NSDate *)canceledAt;

@end

NS_ASSUME_NONNULL_END
