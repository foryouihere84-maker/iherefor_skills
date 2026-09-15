//
//  SceneDelegate.m
//  testUIProject
//
//  The root screen is a navigation controller whose root is ViewController: a list of
//  every page in the project. Tapping a cell pushes the matching view controller.
//  Only the owner of the window moved from AppDelegate to the scene delegate.
//

#import "SceneDelegate.h"
#import "ViewController.h"

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
    // 根控制器改为「工程页清单」：ViewController 是一个列表，
    // 列出所有页面，点击任意一行 push 到对应视图。
    ViewController *root = [[ViewController alloc] init];
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:root];
    self.window.rootViewController = nav;
    [self.window makeKeyAndVisible];
}

- (void)sceneDidDisconnect:(UIScene *)scene {
    // The scene is being released: drop the window so no stale UIWindow keeps the
    // abandoned scene (and its views) alive.
    self.window = nil;
}

- (void)sceneDidBecomeActive:(UIScene *)scene {
    // 运行时设备尺寸探针，只在 IHEREFOR_PROBE_DEVICE=1 时输出（由 UI 测试的
    // launchEnvironment 打开）。
    //
    // **必须在 App 进程里读。** UI 测试进程是另一个 app，它的 Info.plist 由 Xcode 自动
    // 生成、没有 `UILaunchScreen`，在 iPad 上会被 iOS 放进 768x1024 的兼容画布 —— 从测试
    // 进程调 `[UIScreen mainScreen]` 拿到的是 runner 的屏幕，不是被测 App 的屏幕。实测同一台
    // iPad (10th generation)：runner 读到 768x1024，App 读到 820x1180，差 8%。这个值一旦
    // 写进 runtime-device.json，整条 mapper 链从第一步就是错的。
    if ([NSProcessInfo.processInfo.environment[@"IHEREFOR_PROBE_DEVICE"] isEqualToString:@"1"]) {
        UIWindowScene *windowScene = (UIWindowScene *)self.window.windowScene;
        CGSize screen = UIScreen.mainScreen.bounds.size;
        CGSize window = self.window.bounds.size;
        CGSize sceneBounds = windowScene.coordinateSpace.bounds.size;
        CGSize rootView = self.window.rootViewController.view.bounds.size;
        NSLog(@"IHEREFOR_EVENT device-probe screen=%.1fx%.1f window=%.1fx%.1f "
              @"scene=%.1fx%.1f rootView=%.1fx%.1f scale=%.2f",
              screen.width, screen.height,
              window.width, window.height,
              sceneBounds.width, sceneBounds.height,
              rootView.width, rootView.height,
              UIScreen.mainScreen.scale);
    }

    // TODO: connect business action - resume work paused while the scene was inactive.
}

- (void)sceneWillResignActive:(UIScene *)scene {
    // TODO: connect business action - pause work while the scene is inactive.
}

- (void)sceneWillEnterForeground:(UIScene *)scene {
    // TODO: connect business action - undo background-state changes.
}

- (void)sceneDidEnterBackground:(UIScene *)scene {
    // TODO: connect business action - persist state before suspension.
}

@end
