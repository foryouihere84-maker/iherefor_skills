import XCTest
@testable import ReaderApp

final class LibraryViewModelTests: XCTestCase {

    private var repo: InMemoryLibraryRepository!
    private var vm: LibraryViewModel!

    override func setUp() {
        super.setUp()
        repo = InMemoryLibraryRepository()
        vm = LibraryViewModel(repository: repo)
    }

    // shouldRejectUnsupportedFormat (at VM level)
    func testImportUnsupportedFormatReturnsError() {
        let err = vm.importBook(ext: "mobi", sourceUri: "file:///a.mobi", title: "A")
        XCTAssertEqual(err, "不支持的格式")
        XCTAssertEqual(vm.books().count, 0)
    }

    // shouldDedupeBySourceUri
    func testImportDuplicateSourceUriDoesNotAddSecond() {
        _ = vm.importBook(ext: "epub", sourceUri: "file:///a.epub", title: "A")
        let err = vm.importBook(ext: "epub", sourceUri: "file:///a.epub", title: "A2")
        XCTAssertEqual(err, "已存在")
        XCTAssertEqual(vm.books().count, 1)
    }

    func testImportAddsBook() {
        let err = vm.importBook(ext: "txt", sourceUri: "file:///b.txt", title: "B")
        XCTAssertNil(err)
        XCTAssertEqual(vm.books().count, 1)
        XCTAssertEqual(vm.books().first?.format, .txt)
    }

    // shouldRemoveBookAndProgressOnDelete
    func testRemoveBookRemovesRecord() {
        _ = vm.importBook(ext: "pdf", sourceUri: "file:///c.pdf", title: "C")
        let id = vm.books().first!.id
        vm.removeBook(id: id)
        XCTAssertEqual(vm.books().count, 0)
    }

    // shouldVerifyProgressFormatCompatibility (at VM level)
    func testSaveIncompatibleProgressIsIgnored() {
        _ = vm.importBook(ext: "pdf", sourceUri: "file:///c.pdf", title: "C")
        let id = vm.books().first!.id
        let chapterProgress = ReadingProgress(bookId: id, locatorType: .chapter,
                                              chapterIndex: 0, offset: 0,
                                              pageIndex: nil, updatedAt: Date())
        vm.saveProgress(bookId: id, progress: chapterProgress)
        XCTAssertNil(vm.books().first?.progress)
    }
}
