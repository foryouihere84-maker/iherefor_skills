//
//  STSubscription.m
//  SubTracker
//

#import "STSubscription.h"

@implementation STSubscription

- (instancetype)initWithName:(NSString *)name
                  priceCents:(NSInteger)priceCents
                       cycle:(STBillingCycle)cycle
                   startedAt:(NSDate *)startedAt
                 trialEndsAt:(NSDate *)trialEndsAt
                  canceledAt:(NSDate *)canceledAt {
    self = [super init];
    if (self) {
        _name = [name copy];
        _priceCents = priceCents;
        _cycle = cycle;
        _startedAt = startedAt;
        _trialEndsAt = trialEndsAt;
        _canceledAt = canceledAt;
    }
    return self;
}

@end
