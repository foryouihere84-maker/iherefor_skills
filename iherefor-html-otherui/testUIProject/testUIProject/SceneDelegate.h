//
//  SceneDelegate.h
//  testUIProject
//
//  UIScene lifecycle owner. UIKit hands every connecting UIWindowScene to this
//  delegate (declared in Info.plist -> UIApplicationSceneManifest), and the
//  delegate owns the window that used to live on AppDelegate.
//

#import <UIKit/UIKit.h>

@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>

@property (nonatomic, strong) UIWindow *window;

@end
