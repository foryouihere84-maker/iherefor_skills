import Foundation

/// 可替换解析 seam（对齐 跨端共享层契约，未来可换 Readium）
protocol BookParser {
    /// 从字节流解析出文档流（章节序列）。失败抛错。
    func parse(data: Data) throws -> ParsedBook
}
