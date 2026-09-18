//
//  SceneDelegate.m
//  testUIProject
//
//  The root screen is a navigation controller whose root is ViewController: a clean
//  skeleton entry list. Pages will be re-implemented later.
//

#import "SceneDelegate.h"
#import "ViewController.h"
#import "SubscriptionPaywallViewController.h"
#import "SplashViewController.h"
#import "WelcomeViewController.h"
#import "PurposeOnboardingViewController.h"
@implementation SceneDelegate

- (void)scene:(UIScene *)scene
    willConnectToSession:(UISceneSession *)session
                 options:(UISceneConnectionOptions *)connectionOptions {
    if (![scene isKindOfClass:[UIWindowScene class]]) {
        return;
    }
    UIWindowScene *windowScene = (UIWindowScene *)scene;
    self.window = [[UIWindow alloc] initWithWindowScene:windowScene];
    self.window.frame = windowScene.coordinateSpace.bounds;

    // 根页面：启动页。完整流程为 启动→欢迎→引导(目的/性别/年龄/风格/笔刷/色板/完成)。
    SplashViewController *root = [[SplashViewController alloc] init];
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:root];
    nav.navigationBarHidden = YES;
    self.window.rootViewController = nav;
    [self.window makeKeyAndVisible];
}

- (void)sceneDidDisconnect:(UIScene *)scene {
    self.window = nil;
}

- (void)sceneDidBecomeActive:(UIScene *)scene {
}

- (void)sceneWillResignActive:(UIScene *)scene {
}

- (void)sceneWillEnterForeground:(UIScene *)scene {
}

- (void)sceneDidEnterBackground:(UIScene *)scene {
}

@end
