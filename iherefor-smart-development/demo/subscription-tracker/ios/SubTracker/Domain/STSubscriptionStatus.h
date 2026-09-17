//
//  STSubscriptionStatus.h
//  SubTracker
//

#import <Foundation/Foundation.h>

typedef NS_ENUM(NSInteger, STSubscriptionStatus) {
    STSubscriptionStatusTrial = 0,
    STSubscriptionStatusActive = 1,
    STSubscriptionStatusExpired = 2,
    STSubscriptionStatusCanceled = 3,
};
