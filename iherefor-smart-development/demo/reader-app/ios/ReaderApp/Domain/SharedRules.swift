import Foundation

/// 共享纯函数领域规则（跨端一致语义，两端各自实现同义函数）
enum SharedRules {

    /// 支持的格式集合
    static let supportedFormats: Set<BookFormat> = Set(BookFormat.allCases)

    /// 从原始格式字符串识别 BookFormat；返回 nil 表示不支持
    static func detectFormat(fromExtension ext: String) -> BookFormat? {
        let normalized = ext.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        switch normalized {
        case "epub": return .epub
        case "pdf": return .pdf
        case "txt", "text": return .txt
        default: return nil
        }
    }

    /// 是否支持该格式
    static func isSupported(_ format: BookFormat) -> Bool {
        supportedFormats.contains(format)
    }

    /// 进度↔格式兼容校验（共享不变量 #4）
    static func isProgressCompatible(format: BookFormat, progress: ReadingProgress) -> Bool {
        switch format {
        case .pdf:
            return progress.locatorType == .page
        case .epub, .txt:
            return progress.locatorType == .chapter
        }
    }

    /// 按 sourceUri 去重（共享不变量 #6）：返回已有书，若不存在
    static func findDuplicate(sourceUri: String, in books: [Book]) -> Book? {
        books.first { $0.sourceUri == sourceUri }
    }
}
