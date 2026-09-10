#import "AppDelegate.h"
#import "SubscriptionPlanSelectionViewController.h"
@implementation AppDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions { self.window=[[UIWindow alloc]initWithFrame:UIScreen.mainScreen.bounds]; self.window.rootViewController=[SubscriptionPlanSelectionViewController new]; [self.window makeKeyAndVisible]; return YES; }
@end
