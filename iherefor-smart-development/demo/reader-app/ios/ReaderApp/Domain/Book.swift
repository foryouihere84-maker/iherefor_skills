import Foundation

/// 书籍格式（共享契约，取值与 跨端共享层.md 一致）
enum BookFormat: String, Codable, CaseIterable {
    case epub
    case pdf
    case txt

    /// 该格式对应的进度定位类型
    var locatorType: LocatorType {
        switch self {
        case .pdf: return .page
        case .epub, .txt: return .chapter
        }
    }
}

/// 进度定位类型（共享契约）
enum LocatorType: String, Codable {
    case chapter
    case page
}

/// 阅读进度
struct ReadingProgress: Codable, Equatable {
    var bookId: String
    var locatorType: LocatorType
    var chapterIndex: Int?
    var offset: Int?
    var pageIndex: Int?
    var updatedAt: Date

    /// 越界回退：把越界的定位回退到起点（第 0 章 / 第 0 页）
    mutating func clamp(within chapters: Int, pages: Int) {
        switch locatorType {
        case .chapter:
            if let idx = chapterIndex {
                if idx < 0 || idx >= chapters { chapterIndex = 0 }
            }
        case .page:
            if let idx = pageIndex {
                if idx < 0 || idx >= pages { pageIndex = 0 }
            }
        }
    }
}

/// 书籍实体
struct Book: Identifiable, Codable, Equatable {
    var id: String
    var title: String
    var author: String?
    var format: BookFormat
    var sourceUri: String
    var coverUri: String?
    var importedAt: Date
    var progress: ReadingProgress?
}

/// 章节
struct Chapter: Identifiable, Equatable {
    var index: Int
    var title: String
    var content: String
    var id: Int { index }
}

/// 解析结果：文档流（章节序列）
struct ParsedBook: Equatable {
    var chapters: [Chapter]
}
