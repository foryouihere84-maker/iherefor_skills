//
//  AppDelegate.m
//  testUIProject
//

#import "AppDelegate.h"

@implementation AppDelegate

- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    // Window creation lives in SceneDelegate: UIKit requires the UIScene lifecycle
    // and builds every window from a connecting UIWindowScene.
    return YES;
}

#pragma mark - UISceneSession lifecycle

- (UISceneConfiguration *)application:(UIApplication *)application
    configurationForConnectingSceneSession:(UISceneSession *)connectingSceneSession
                                   options:(UISceneConnectionOptions *)options {
    // Resolves the "Default Configuration" entry declared in Info.plist, which is
    // what binds the connecting scene to SceneDelegate.
    return [[UISceneConfiguration alloc] initWithName:@"Default Configuration"
                                          sessionRole:connectingSceneSession.role];
}

- (void)application:(UIApplication *)application didDiscardSceneSessions:(NSSet<UISceneSession *> *)sceneSessions {
    // TODO: connect business action - release resources held for discarded scenes.
}

@end
