#import <XCTest/XCTest.h>

@interface SmokeUITests : XCTestCase
@end

@implementation SmokeUITests
- (void)testLaunch { XCUIApplication *app = [[XCUIApplication alloc] init]; [app launch]; XCTAssertTrue(app.exists); }
@end
