//
//  StyleSelectionViewController.m
//  testUIProject
//

#import "StyleSelectionViewController.h"
#import "StyleSelectionFooterView.h"
#import "StyleSelectionGridRegionView.h"
#import "StyleSelectionHeroView.h"
#import "StyleSelectionOptionRowView.h"
#import "StyleSelectionStyle.h"

/// The design's first step fills 24pt of the 232pt track.
static const CGFloat kProgressFillStepDesignWidth = 24.0;

@interface StyleSelectionViewController ()
@property(nonatomic, strong) StyleSelectionStyle *style;
@property(nonatomic, strong) UIView *canvasView;
@property(nonatomic, strong) StyleSelectionHeroView *heroView;
@property(nonatomic, strong) StyleSelectionGridRegionView *gridRegionView;
@property(nonatomic, copy) NSArray<StyleSelectionOptionRowView *> *optionRows;
@property(nonatomic, strong) StyleSelectionFooterView *footerView;
@property(nonatomic, assign) StyleSelectionOption selectedOption;
@property(nonatomic, assign) BOOL hasBuiltRegions;
@end

@implementation StyleSelectionViewController

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];

    self.view.backgroundColor = StyleSelectionStyle.pageBackgroundColor;
    // The design's hero artwork starts at canvas y=0 and its status band is a mock for
    // the real one, so the page runs underneath the system bars.
    self.edgesForExtendedLayout = UIRectEdgeAll;
    self.extendedLayoutIncludesOpaqueBars = YES;
    self.selectedOption = StyleSelectionOptionNone;

    NSLog(@"IHEREFOR_RUNTIME_SCREEN_BOUNDS width=%.4f height=%.4f scale=%.4f nativeScale=%.4f",
          UIScreen.mainScreen.bounds.size.width, UIScreen.mainScreen.bounds.size.height,
          UIScreen.mainScreen.scale, UIScreen.mainScreen.nativeScale);

    [self buildRegions];
    [StyleSelectionStyle logClosureCounters];
}

- (UIStatusBarStyle)preferredStatusBarStyle {
    return UIStatusBarStyleDarkContent;
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];

    UIEdgeInsets insets = self.view.safeAreaInsets;
    CGSize viewSize = self.view.bounds.size;
    NSLog(@"IHEREFOR_RUNTIME_VIEW_BOUNDS width=%.4f height=%.4f safeTop=%.4f safeBottom=%.4f "
          @"canvasDesignW=%.4f canvasDesignH=%.4f uniformScale=%.8f policy=fit",
          viewSize.width, viewSize.height, insets.top, insets.bottom,
          kStyleSelectionCanvasWidth, kStyleSelectionCanvasHeight,
          viewSize.width / kStyleSelectionCanvasWidth);

    [self logRegionFrames];
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];
    NSLog(@"IHEREFOR_RUNTIME_READY page=style-selection");
    [self logRegionFrames];
}

#pragma mark - Region assembly

- (void)buildRegions {
    if (self.hasBuiltRegions) {
        return;
    }
    self.hasBuiltRegions = YES;

    self.style = [StyleSelectionStyle new];

    // The Lanhu canvas is a fixed 393x852 board, so it is closed onto the window with
    // the `fit` policy: one uniform scale derived from the window width, centred
    // vertically, with the leftover split into equal bands. Closing the height onto the
    // window HEIGHT instead would stretch every child by 0.28%.
    self.canvasView = [[UIView alloc] initWithFrame:CGRectZero];
    self.canvasView.backgroundColor = StyleSelectionStyle.pageBackgroundColor;
    self.canvasView.clipsToBounds = NO;
    self.canvasView.accessibilityIdentifier = @"styleSelection.canvas";
    [self.view addSubview:self.canvasView];
    [NSLayoutConstraint activateConstraints:[StyleSelectionStyle fitCanvas:self.canvasView
                                                               insideView:self.view]];

    // --- hero (canvas 0,0,393,365) ---------------------------------------------
    StyleSelectionOptionRowView *topRow = [self makeRowWithLeft:[self specForOption:StyleSelectionOptionAnimal]
                                                          right:[self specForOption:StyleSelectionOptionManga]];
    self.heroView = [[StyleSelectionHeroView alloc] initWithStyle:self.style topOptionRowView:topRow];
    self.heroView.accessibilityIdentifier = @"styleSelection.hero";
    [self.canvasView addSubview:self.heroView];
    [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:self.heroView
                                                                    parent:self.canvasView
                                                               designFrame:CGRectMake(0.0, 0.0,
                                                                                      kStyleSelectionCanvasWidth,
                                                                                      365.0)
                                                          parentDesignSize:CGSizeMake(kStyleSelectionCanvasWidth,
                                                                                      kStyleSelectionCanvasHeight)]];

    // --- lower region (canvas 0,365,393,487) -----------------------------------
    NSMutableArray<StyleSelectionOptionRowView *> *rows = [NSMutableArray arrayWithObject:topRow];
    [rows addObject:[self makeRowWithLeft:[self specForOption:StyleSelectionOptionPeople]
                                    right:[self specForOption:StyleSelectionOptionCute]]];
    [rows addObject:[self makeRowWithLeft:[self specForOption:StyleSelectionOptionFood]
                                    right:[self specForOption:StyleSelectionOptionMandala]]];
    [rows addObject:[self makeRowWithLeft:[self specForOption:StyleSelectionOptionFlower]
                                    right:[self specForOption:StyleSelectionOptionEasy]]];
    self.optionRows = rows;

    self.footerView = [[StyleSelectionFooterView alloc] initWithStyle:self.style];
    self.gridRegionView = [[StyleSelectionGridRegionView alloc] initWithStyle:self.style
                                                                        rows:@[rows[1], rows[2], rows[3]]
                                                                      footer:self.footerView];
    self.gridRegionView.accessibilityIdentifier = @"styleSelection.lowerRegion";
    [self.canvasView addSubview:self.gridRegionView];
    [NSLayoutConstraint activateConstraints:[StyleSelectionStyle closeChild:self.gridRegionView
                                                                    parent:self.canvasView
                                                               designFrame:CGRectMake(0.0, 365.0,
                                                                                      kStyleSelectionCanvasWidth,
                                                                                      487.0)
                                                          parentDesignSize:CGSizeMake(kStyleSelectionCanvasWidth,
                                                                                      kStyleSelectionCanvasHeight)]];

    [self connectInteractions];
    [self refreshSelectionRings];
    [self.heroView.navRowView setProgressFillDesignWidth:kProgressFillStepDesignWidth];
}

/// The eight cards of the page, declared once. The three right-hand cards in the lower
/// grid ship their label scrim already composited into the artwork, and their labels sit
/// directly on the card instead of inside a chip.
- (StyleSelectionOptionSpec *)specForOption:(StyleSelectionOption)option {
    switch (option) {
        case StyleSelectionOptionAnimal:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_animal_art"
                                                  chipScrim:@"style_selection_option_chip_scrim"
                                                      label:@"Animal"
                                           labelDesignFrame:CGRectMake(57.0, 34.0, 56.0, 22.0)
                                             labelStyleName:@"cardLabelAnimal"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.animal"];
        case StyleSelectionOptionManga:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_manga_art"
                                                  chipScrim:@"style_selection_option_chip_scrim"
                                                      label:@"Manga"
                                           labelDesignFrame:CGRectMake(57.0, 34.0, 56.0, 22.0)
                                             labelStyleName:@"cardLabelManga"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.manga"];
        case StyleSelectionOptionPeople:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_people_art"
                                                  chipScrim:@"style_selection_option_chip_scrim"
                                                      label:@"People"
                                           labelDesignFrame:CGRectMake(56.0, 36.0, 56.70, 22.0)
                                             labelStyleName:@"cardLabelPeople"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.people"];
        case StyleSelectionOptionCute:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_cute_art"
                                                  chipScrim:nil
                                                      label:@"Cute"
                                           labelDesignFrame:CGRectMake(65.64, 114.0, 39.36, 22.0)
                                             labelStyleName:@"cardLabelCute"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.cute"];
        case StyleSelectionOptionFood:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_food_art"
                                                  chipScrim:@"style_selection_option_chip_scrim"
                                                      label:@"Food"
                                           labelDesignFrame:CGRectMake(63.0, 36.0, 42.72, 22.0)
                                             labelStyleName:@"cardLabelFood"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.food"];
        case StyleSelectionOptionMandala:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_mandala_art"
                                                  chipScrim:nil
                                                      label:@"Mandala"
                                           labelDesignFrame:CGRectMake(50.33, 114.0, 69.67, 22.0)
                                             labelStyleName:@"cardLabelMandala"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.mandala"];
        case StyleSelectionOptionFlower:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_flower_art"
                                                  chipScrim:@"style_selection_option_chip_scrim"
                                                      label:@"Flower"
                                           labelDesignFrame:CGRectMake(57.0, 36.0, 55.69, 22.0)
                                             labelStyleName:@"cardLabelFlower"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.flower"];
        case StyleSelectionOptionEasy:
            return [StyleSelectionOptionSpec specWithOption:option
                                                        art:@"style_selection_option_easy_art"
                                                  chipScrim:nil
                                                      label:@"Easy"
                                           labelDesignFrame:CGRectMake(66.66, 114.0, 37.34, 22.0)
                                             labelStyleName:@"cardLabelEasy"
                                                weightClass:StyleSelectionFontWeightClassMedium
                                    accessibilityIdentifier:@"styleSelection.option.easy"];
        case StyleSelectionOptionNone:
        default:
            break;
    }
    return [StyleSelectionOptionSpec specWithOption:StyleSelectionOptionNone
                                                art:@""
                                          chipScrim:nil
                                              label:@""
                                   labelDesignFrame:CGRectZero
                                     labelStyleName:@""
                                        weightClass:StyleSelectionFontWeightClassMedium
                            accessibilityIdentifier:@"styleSelection.option.unused"];
}

- (StyleSelectionOptionRowView *)makeRowWithLeft:(StyleSelectionOptionSpec *)left
                                           right:(StyleSelectionOptionSpec *)right {
    return [[StyleSelectionOptionRowView alloc] initWithStyle:self.style left:left right:right];
}

#pragma mark - Interaction

- (void)connectInteractions {
    [self.heroView.navRowView.backButton addTarget:self
                                            action:@selector(didTapBack:)
                                  forControlEvents:UIControlEventTouchUpInside];
    [self.heroView.navRowView.skipButton addTarget:self
                                            action:@selector(didTapSkip:)
                                  forControlEvents:UIControlEventTouchUpInside];
    [self.footerView.continueButton addTarget:self
                                       action:@selector(didTapContinue:)
                             forControlEvents:UIControlEventTouchUpInside];

    for (StyleSelectionOptionRowView *row in self.optionRows) {
        for (StyleSelectionOptionCardView *card in row.cards) {
            [card addTarget:self
                     action:@selector(didTapOptionCard:)
           forControlEvents:UIControlEventTouchUpInside];
        }
    }
}

- (void)didTapOptionCard:(StyleSelectionOptionCardView *)sender {
    switch (sender.option) {
        case StyleSelectionOptionAnimal:   [self didTapAnimal:sender];   break;
        case StyleSelectionOptionManga:    [self didTapManga:sender];    break;
        case StyleSelectionOptionPeople:   [self didTapPeople:sender];   break;
        case StyleSelectionOptionCute:     [self didTapCute:sender];     break;
        case StyleSelectionOptionFood:     [self didTapFood:sender];     break;
        case StyleSelectionOptionMandala:  [self didTapMandala:sender];  break;
        case StyleSelectionOptionFlower:   [self didTapFlower:sender];   break;
        case StyleSelectionOptionEasy:     [self didTapEasy:sender];     break;
        case StyleSelectionOptionNone:
        default: break;
    }
}

- (void)selectOption:(StyleSelectionOption)option {
    self.selectedOption = option;
    [self refreshSelectionRings];
    NSLog(@"IHEREFOR_SELECTION option=%ld", (long)option);
}

- (void)refreshSelectionRings {
    for (StyleSelectionOptionRowView *row in self.optionRows) {
        for (StyleSelectionOptionCardView *card in row.cards) {
            card.ringVisible = (card.option == self.selectedOption);
        }
    }
}

#pragma mark - Named handlers (business not wired yet)

- (void)didTapBack:(id)sender {
    // TODO: connect business action - return to the previous screen.
}

- (void)didTapSkip:(id)sender {
    // TODO: connect business action - skip style selection.
}

- (void)didTapAnimal:(id)sender {
    [self selectOption:StyleSelectionOptionAnimal];
    // TODO: connect business action - record the animal style choice.
}

- (void)didTapManga:(id)sender {
    [self selectOption:StyleSelectionOptionManga];
    // TODO: connect business action - record the manga style choice.
}

- (void)didTapPeople:(id)sender {
    [self selectOption:StyleSelectionOptionPeople];
    // TODO: connect business action - record the people style choice.
}

- (void)didTapCute:(id)sender {
    [self selectOption:StyleSelectionOptionCute];
    // TODO: connect business action - record the cute style choice.
}

- (void)didTapFood:(id)sender {
    [self selectOption:StyleSelectionOptionFood];
    // TODO: connect business action - record the food style choice.
}

- (void)didTapMandala:(id)sender {
    [self selectOption:StyleSelectionOptionMandala];
    // TODO: connect business action - record the mandala style choice.
}

- (void)didTapFlower:(id)sender {
    [self selectOption:StyleSelectionOptionFlower];
    // TODO: connect business action - record the flower style choice.
}

- (void)didTapEasy:(id)sender {
    [self selectOption:StyleSelectionOptionEasy];
    // TODO: connect business action - record the easy style choice.
}

- (void)didTapContinue:(id)sender {
    // TODO: connect business action - advance with the selected style.
}

#pragma mark - Runtime geometry logging

- (void)logRegionFrames {
    UIWindow *window = self.view.window;
    if (!window) {
        return;
    }
    NSArray<NSString *> *identifiers = @[
        @"styleSelection.canvas", @"styleSelection.hero", @"styleSelection.nav",
        @"styleSelection.progress.track", @"styleSelection.progress.fill",
        @"styleSelection.nav.back", @"styleSelection.nav.skip",
        @"styleSelection.headline", @"styleSelection.row.top",
        @"styleSelection.lowerRegion", @"styleSelection.bottomScrim",
        @"styleSelection.continue",
    ];
    for (NSString *identifier in identifiers) {
        UIView *view = [self viewWithAccessibilityIdentifier:identifier inView:window];
        if (!view) {
            NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ status=missing", identifier);
            continue;
        }
        CGRect frame = [view convertRect:view.bounds toView:self.view];
        NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ class=%@ frameInRoot=%.3f,%.3f,%.3f,%.3f alpha=%.2f hidden=%d",
              identifier, NSStringFromClass(view.class), frame.origin.x, frame.origin.y,
              frame.size.width, frame.size.height, view.alpha, view.hidden);
    }

    for (StyleSelectionOptionRowView *row in self.optionRows) {
        for (StyleSelectionOptionCardView *card in row.cards) {
            CGRect frame = [card convertRect:card.bounds toView:self.view];
            NSLog(@"IHEREFOR_REGION_GEOMETRY id=%@ class=%@ frameInRoot=%.3f,%.3f,%.3f,%.3f ringVisible=%d",
                  card.accessibilityIdentifier, NSStringFromClass(card.class),
                  frame.origin.x, frame.origin.y, frame.size.width, frame.size.height,
                  card.isRingVisible);
        }
    }

    [self logImagesInView:self.view];
}

- (nullable UIView *)viewWithAccessibilityIdentifier:(NSString *)identifier inView:(UIView *)view {
    if ([view.accessibilityIdentifier isEqualToString:identifier]) {
        return view;
    }
    for (UIView *subview in view.subviews) {
        UIView *match = [self viewWithAccessibilityIdentifier:identifier inView:subview];
        if (match) {
            return match;
        }
    }
    return nil;
}

- (void)logImagesInView:(UIView *)view {
    if ([view isKindOfClass:[UIImageView class]]) {
        UIImageView *imageView = (UIImageView *)view;
        CGRect frameInWindow = [imageView convertRect:imageView.bounds toView:self.view];
        NSLog(@"IHEREFOR_LAYER_IMAGE id=%@ frameInRoot=%.3f,%.3f,%.3f,%.3f bounds=%.3f,%.3f,%.3f,%.3f "
              @"naturalW=%.0f naturalH=%.0f contentMode=%ld alpha=%.2f",
              imageView.accessibilityIdentifier ?: @"<none>",
              frameInWindow.origin.x, frameInWindow.origin.y,
              frameInWindow.size.width, frameInWindow.size.height,
              imageView.bounds.origin.x, imageView.bounds.origin.y,
              imageView.bounds.size.width, imageView.bounds.size.height,
              imageView.image.size.width, imageView.image.size.height,
              (long)imageView.contentMode, imageView.alpha);
    }
    for (UIView *subview in view.subviews) {
        [self logImagesInView:subview];
    }
}

@end
