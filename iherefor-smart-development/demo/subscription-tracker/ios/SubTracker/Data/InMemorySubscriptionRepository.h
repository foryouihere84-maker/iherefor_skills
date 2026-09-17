//
//  InMemorySubscriptionRepository.h
//  SubTracker
//

#import <Foundation/Foundation.h>

@class STSubscription;

NS_ASSUME_NONNULL_BEGIN

/// Repository seam 的内存 adapter（对应 shared-layer.md 的 Repository 接口），仅 all()。
@interface InMemorySubscriptionRepository : NSObject

- (instancetype)initWithSubscriptions:(NSArray<STSubscription *> *)subscriptions;
- (NSArray<STSubscription *> *)all;

@end

NS_ASSUME_NONNULL_END
