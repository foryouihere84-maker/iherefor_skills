//
//  InMemorySubscriptionRepository.m
//  SubTracker
//

#import "InMemorySubscriptionRepository.h"
#import "STSubscription.h"

@implementation InMemorySubscriptionRepository {
    NSArray<STSubscription *> *_subscriptions;
}

- (instancetype)initWithSubscriptions:(NSArray<STSubscription *> *)subscriptions {
    self = [super init];
    if (self) {
        _subscriptions = [subscriptions copy];
    }
    return self;
}

- (NSArray<STSubscription *> *)all {
    return _subscriptions;
}

@end
