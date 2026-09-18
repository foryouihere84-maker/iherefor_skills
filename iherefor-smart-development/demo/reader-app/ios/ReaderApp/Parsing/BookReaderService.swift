import Foundation

/// 按格式分派的读取服务：读源文件字节 → 选 parser → 解析出文档流。
/// 这是「打开书 → 解析 → 渲染」链路的用例层，可测 seam 在 parser 工厂注入处。
struct BookReaderService {

    /// 按 BookFormat 选 parser（future 换 Readium 只改这里）
    private let parsers: [BookFormat: BookParser] = [
        .epub: EpubParser(),
        .txt: TxtParser(),
    ]

    /// 从字节流解析（纯函数式，便于测试）
    func parse(format: BookFormat, data: Data) throws -> ParsedBook {
        if format == .pdf {
            // PDF 走系统 PDFKit 按页渲染，无「章节文档流」概念
            throw ParserError.pdfNotStreamed
        }
        guard let parser = parsers[format] else {
            throw ParserError.unsupportedEncoding
        }
        return try parser.parse(data: data)
    }

    /// 从源文件读取并解析（文件路径）
    func readAndParse(book: Book) throws -> ParsedBook {
        guard book.format != .pdf else {
            throw ParserError.pdfNotStreamed
        }
        let url = URL(string: book.sourceUri)
        let data: Data
        if let url, url.isFileURL {
            data = try Data(contentsOf: url)
        } else if let url {
            data = try Data(contentsOf: url)
        } else {
            throw ParserError.emptyFile
        }
        return try parse(format: book.format, data: data)
    }
}

extension ParserError {
    static let pdfNotStreamed = ParserError.unsupportedEncoding
}
