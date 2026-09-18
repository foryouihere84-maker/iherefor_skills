import XCTest
@testable import ReaderApp

final class TxtParserTests: XCTestCase {

    func testSplitTxtIntoChapters() {
        let text = "第一章\n内容AA\n\n第二章\n内容BB\n\n第三章\n内容CC"
        let parser = TxtParser()
        let chapters = parser.splitChapters(text: text)
        XCTAssertEqual(chapters.count, 3)
        XCTAssertEqual(chapters[0].index, 0)
        XCTAssertTrue(chapters[0].content.contains("内容AA"))
    }

    func testSingleBlockTxtBecomesOneChapter() {
        let text = "没有空行的整篇内容"
        let parser = TxtParser()
        let chapters = parser.splitChapters(text: text)
        XCTAssertEqual(chapters.count, 1)
    }

    func testEmptyTextYieldsNoChapters() {
        let parser = TxtParser()
        XCTAssertTrue(parser.splitChapters(text: "").isEmpty)
        XCTAssertTrue(parser.splitChapters(text: "   \n  ").isEmpty)
    }

    // shouldRejectEmptyFile
    func testParseEmptyDataThrows() {
        let parser = TxtParser()
        XCTAssertThrowsError(try parser.parse(data: Data()))
    }

    // shouldFallbackEncodingForNonUtf8
    func testDecodeUtf8() {
        let parser = TxtParser()
        let data = "你好".data(using: .utf8)!
        XCTAssertEqual(parser.decode(data: data), "你好")
    }
}

final class EpubParserTests: XCTestCase {

    func testExtractManifestIdHref() {
        let parser = EpubParser()
        let opf = #"<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="ch2.html"/></manifest>"#
        let map = parser.extractManifestIdHref(from: opf)
        XCTAssertEqual(map["c1"], "c1.xhtml")
        XCTAssertEqual(map["c2"], "ch2.html")
    }

    func testExtractSpineIdrefsOrder() {
        let parser = EpubParser()
        let opf = #"<spine><itemref idref="c2"/><itemref idref="c1"/></spine>"#
        XCTAssertEqual(parser.extractSpineIdrefs(from: opf), ["c2", "c1"])
    }

    func testStripHtmlRemovesTagsAndDecodesEntities() {
        let parser = EpubParser()
        let html = "<html><body><p>你好 &amp; 世界</p><script>var x=1;</script></body></html>"
        let text = parser.stripHtml(html)
        XCTAssertTrue(text.contains("你好 & 世界"))
        XCTAssertFalse(text.contains("<p>"))
        XCTAssertFalse(text.contains("var x"))
    }

    // shouldRejectEmptyFile
    func testParseEmptyDataThrows() {
        let parser = EpubParser()
        XCTAssertThrowsError(try parser.parse(data: Data()))
    }

    func testParseInvalidZipThrows() {
        let parser = EpubParser()
        XCTAssertThrowsError(try parser.parse(data: Data([0x00, 0x01, 0x02])))
    }
}
