//
//  SceneDelegate.m
//  testUIProject
//
//  The root screen is unchanged from the pre-UIScene implementation: the special
//  offer paywall is the only window content. Only the owner of the window moved
//  from AppDelegate to the scene delegate.
//

#import "SceneDelegate.h"
#import "SpecialOfferViewController.h"

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
    self.window.rootViewController = [SpecialOfferViewController new];
    [self.window makeKeyAndVisible];
}

- (void)sceneDidDisconnect:(UIScene *)scene {
    // The scene is being released: drop the window so no stale UIWindow keeps the
    // abandoned scene (and its views) alive.
    self.window = nil;
}

- (void)sceneDidBecomeActive:(UIScene *)scene {
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
