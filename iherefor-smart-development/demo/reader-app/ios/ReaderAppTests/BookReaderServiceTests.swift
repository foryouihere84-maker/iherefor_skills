import XCTest
@testable import ReaderApp

/// BookReaderService 分派测试：验证「打开书 → 按格式解析 → 文档流」链路
final class BookReaderServiceTests: XCTestCase {

    private let service = BookReaderService()

    func testParseTxtDispatchesToTxtParser() throws {
        let txt = "第一章\n内容AA\n\n第二章\n内容BB"
        let data = txt.data(using: .utf8)!
        let parsed = try service.parse(format: .txt, data: data)
        XCTAssertEqual(parsed.chapters.count, 2)
        XCTAssertTrue(parsed.chapters[0].content.contains("内容AA"))
    }

    func testParseEpubDispatchesToEpubParser() throws {
        // 用真实构造的合法 stored ZIP（含正确 central directory + EOCD）
        let epubData = try ZipBuilder.makeEpub(chapters: [
            ("ch1.xhtml", "<html><body><p>第一章 正文</p></body></html>"),
            ("ch2.xhtml", "<html><body><p>第二章 正文</p></body></html>"),
        ])
        let parsed = try service.parse(format: .epub, data: epubData)
        XCTAssertEqual(parsed.chapters.count, 2)
        XCTAssertTrue(parsed.chapters[0].content.contains("第一章 正文"))
    }

    func testParsePdfThrows() {
        XCTAssertThrowsError(try service.parse(format: .pdf, data: Data([0x25, 0x50, 0x44, 0x46])))
    }
}

/// 手工构造 stored（无压缩）ZIP 的工具，含正确的 central directory + EOCD
enum ZipBuilder {

    static func makeEpub(chapters: [(String, String)]) throws -> Data {
        // 内容
        let opfBody = """
        <?xml version="1.0"?>
        <package xmlns="http://www.idpf.org/2007/opf" version="2.0">
          <manifest>
            <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
            <item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
          </manifest>
          <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
        </package>
        """

        var files: [(name: String, data: Data)] = [
            ("mimetype", "application/epub+zip".data(using: .utf8)!),
            ("OEBPS/content.opf", opfBody.data(using: .utf8)!),
        ]
        for (name, body) in chapters {
            files.append(("OEBPS/\(name)", body.data(using: .utf8)!))
        }

        var output = Data()
        var centralDir = Data()
        var offset: UInt32 = 0

        for f in files {
            let (local, crc) = localFileHeader(name: f.name, data: f.data)
            output.append(local)
            output.append(f.data)

            centralDir.append(centralHeader(name: f.name, data: f.data, crc: crc, localOffset: offset))
            offset += UInt32(local.count + f.data.count)
        }

        let cdOffset = offset
        output.append(centralDir)

        // EOCD
        var eocd = Data()
        eocd.append(le32(0x06054B50))
        eocd.append(le16(0))            // disk number
        eocd.append(le16(0))            // central disk
        eocd.append(le16(UInt16(files.count))) // entries on this disk
        eocd.append(le16(UInt16(files.count))) // total entries
        eocd.append(le32(UInt32(centralDir.count)))  // central dir size
        eocd.append(le32(cdOffset))      // central dir offset
        eocd.append(le16(0))            // comment len
        output.append(eocd)
        return output
    }

    private static func localFileHeader(name: String, data: Data) -> (Data, UInt32) {
        let nameBytes = name.data(using: .utf8)!
        let crc = crc32(data)
        var h = Data()
        h.append(le32(0x04034B50))
        h.append(le16(20))               // version needed
        h.append(le16(0))                // flags
        h.append(le16(0))                // method = stored
        h.append(le16(0))                // time
        h.append(le16(0))                // date
        h.append(le32(crc))              // crc32
        h.append(le32(UInt32(data.count)))   // compressed size
        h.append(le32(UInt32(data.count)))   // uncompressed size
        h.append(le16(UInt16(nameBytes.count))) // name len
        h.append(le16(0))                // extra len
        h.append(nameBytes)
        return (h, crc)
    }

    private static func centralHeader(name: String, data: Data, crc: UInt32, localOffset: UInt32) -> Data {
        let nameBytes = name.data(using: .utf8)!
        var h = Data()
        h.append(le32(0x02014B50))
        h.append(le16(20))               // version made by
        h.append(le16(20))               // version needed
        h.append(le16(0))                // flags
        h.append(le16(0))                // method = stored
        h.append(le16(0))                // time
        h.append(le16(0))                // date
        h.append(le32(crc))              // crc32
        h.append(le32(UInt32(data.count)))   // compressed size
        h.append(le32(UInt32(data.count)))   // uncompressed size
        h.append(le16(UInt16(nameBytes.count))) // name len
        h.append(le16(0))                // extra len
        h.append(le16(0))                // comment len
        h.append(le16(0))                // disk number start
        h.append(le16(0))                // internal attrs
        h.append(le32(0))                // external attrs
        h.append(le32(localOffset))      // local header offset
        h.append(nameBytes)
        return h
    }

    private static func crc32(_ data: Data) -> UInt32 {
        var crc: UInt32 = 0xFFFFFFFF
        for byte in data {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                if crc & 1 != 0 {
                    crc = (crc >> 1) ^ 0xEDB88320
                } else {
                    crc >>= 1
                }
            }
        }
        return crc ^ 0xFFFFFFFF
    }

    private static func le32(_ v: UInt32) -> Data {
        var d = Data()
        d.append(UInt8(v & 0xFF)); d.append(UInt8((v >> 8) & 0xFF))
        d.append(UInt8((v >> 16) & 0xFF)); d.append(UInt8((v >> 24) & 0xFF))
        return d
    }
    private static func le16(_ v: UInt16) -> Data {
        var d = Data()
        d.append(UInt8(v & 0xFF)); d.append(UInt8((v >> 8) & 0xFF))
        return d
    }
}
