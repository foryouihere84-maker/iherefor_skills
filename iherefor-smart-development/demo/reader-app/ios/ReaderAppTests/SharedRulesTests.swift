import XCTest
@testable import ReaderApp

final class SharedRulesTests: XCTestCase {

    // shouldRejectUnsupportedFormat
    func testDetectFormatRejectsUnsupported() {
        XCTAssertNil(SharedRules.detectFormat(fromExtension: "mobi"))
        XCTAssertNil(SharedRules.detectFormat(fromExtension: "azw"))
        XCTAssertNil(SharedRules.detectFormat(fromExtension: ""))
    }

    func testDetectFormatRecognizesSupported() {
        XCTAssertEqual(SharedRules.detectFormat(fromExtension: "epub"), .epub)
        XCTAssertEqual(SharedRules.detectFormat(fromExtension: "PDF"), .pdf)
        XCTAssertEqual(SharedRules.detectFormat(fromExtension: "txt"), .txt)
    }

    // shouldClassifyPdfAsPageLocator
    func testPdfUsesPageLocator() {
        XCTAssertEqual(BookFormat.pdf.locatorType, .page)
    }

    // shouldClassifyEpubAsChapterLocator
    func testEpubAndTxtUseChapterLocator() {
        XCTAssertEqual(BookFormat.epub.locatorType, .chapter)
        XCTAssertEqual(BookFormat.txt.locatorType, .chapter)
    }

    // shouldClampProgressToStartOnOutOfRange
    func testClampProgressOnOutOfRangePage() {
        var p = ReadingProgress(bookId: "1", locatorType: .page,
                                chapterIndex: nil, offset: nil,
                                pageIndex: 99, updatedAt: Date())
        p.clamp(within: 0, pages: 10)
        XCTAssertEqual(p.pageIndex, 0)
    }

    func testClampProgressOnOutOfRangeChapter() {
        var p = ReadingProgress(bookId: "1", locatorType: .chapter,
                                chapterIndex: 50, offset: 3,
                                pageIndex: nil, updatedAt: Date())
        p.clamp(within: 5, pages: 0)
        XCTAssertEqual(p.chapterIndex, 0)
    }

    func testClampKeepsValidProgressIntact() {
        var p = ReadingProgress(bookId: "1", locatorType: .page,
                                chapterIndex: nil, offset: nil,
                                pageIndex: 3, updatedAt: Date())
        p.clamp(within: 0, pages: 10)
        XCTAssertEqual(p.pageIndex, 3)
    }

    // shouldDedupeBySourceUri
    func testDedupeBySourceUri() {
        let a = Book(id: "1", title: "A", author: nil, format: .epub,
                     sourceUri: "file:///a.epub", coverUri: nil,
                     importedAt: Date(), progress: nil)
        let b = Book(id: "2", title: "B", author: nil, format: .txt,
                     sourceUri: "file:///b.txt", coverUri: nil,
                     importedAt: Date(), progress: nil)
        XCTAssertEqual(SharedRules.findDuplicate(sourceUri: "file:///a.epub", in: [a, b])?.id, "1")
        XCTAssertNil(SharedRules.findDuplicate(sourceUri: "file:///c.epub", in: [a, b]))
    }

    // shouldVerifyProgressFormatCompatibility
    func testProgressFormatCompatibility() {
        let pageProgress = ReadingProgress(bookId: "1", locatorType: .page,
                                           chapterIndex: nil, offset: nil,
                                           pageIndex: 0, updatedAt: Date())
        XCTAssertTrue(SharedRules.isProgressCompatible(format: .pdf, progress: pageProgress))
        XCTAssertFalse(SharedRules.isProgressCompatible(format: .epub, progress: pageProgress))

        let chapterProgress = ReadingProgress(bookId: "1", locatorType: .chapter,
                                              chapterIndex: 0, offset: 0,
                                              pageIndex: nil, updatedAt: Date())
        XCTAssertTrue(SharedRules.isProgressCompatible(format: .txt, progress: chapterProgress))
        XCTAssertFalse(SharedRules.isProgressCompatible(format: .pdf, progress: chapterProgress))
    }
}
