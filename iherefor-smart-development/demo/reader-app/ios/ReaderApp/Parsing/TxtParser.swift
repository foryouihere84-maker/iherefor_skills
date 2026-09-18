import Foundation

enum ParserError: LocalizedError {
    case emptyFile
    case unsupportedEncoding

    var errorDescription: String? {
        switch self {
        case .emptyFile: return "文件为空"
        case .unsupportedEncoding: return "无法识别的编码"
        }
    }
}

/// TXT 解析器：按空行切分章节，UTF-8 优先、GBK 兜底。
struct TxtParser: BookParser {

    func parse(data: Data) throws -> ParsedBook {
        guard !data.isEmpty else { throw ParserError.emptyFile }

        let text = decode(data: data)
        let chapters = splitChapters(text: text)
        guard !chapters.isEmpty else { throw ParserError.emptyFile }

        return ParsedBook(chapters: chapters)
    }

    /// 解码：UTF-8 优先，失败回退 GBK（GB18030 兼容 GBK）
    func decode(data: Data) -> String {
        if let s = String(data: data, encoding: .utf8) {
            return s
        }
        let gbk = String.Encoding(rawValue: CFStringConvertEncodingToNSStringEncoding(
            CFStringEncoding(CFStringEncodings.GB_18030_2000.rawValue)))
        if let s = String(data: data, encoding: gbk) {
            return s
        }
        // 最后兜底：有损但总能给出内容
        return String(decoding: data, as: UTF8.self)
    }

    /// 按空行切分章节；无空行时整篇作为单章
    func splitChapters(text: String) -> [Chapter] {
        let normalized = text.replacingOccurrences(of: "\r\n", with: "\n")
        let blocks = normalized
            .components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }

        if blocks.isEmpty {
            let trimmed = normalized.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? [] : [Chapter(index: 0, title: "", content: trimmed)]
        }

        return blocks.enumerated().map { i, content in
            let lines = content.split(separator: "\n", maxSplits: 1)
            let title = lines.count > 1 ? String(lines[0]) : ""
            return Chapter(index: i, title: title, content: content)
        }
    }
}
