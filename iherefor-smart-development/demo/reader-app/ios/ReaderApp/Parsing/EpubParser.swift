import Foundation

/// 自研最小 EPUB 解析器：解 ZIP（MiniZip）→ 找 OPF/NCX → 抽章节 XHTML 纯文本。
/// 首版只抽取章节纯文本，样式/资源不展开（升级预留 Readium）。
struct EpubParser: BookParser {

    func parse(data: Data) throws -> ParsedBook {
        guard !data.isEmpty else { throw ParserError.emptyFile }

        let entries = try MiniZip.unzip(data: data)
        var byName: [String: Data] = [:]
        for e in entries {
            let key = e.name.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            byName[key] = e.data
        }

        guard let opfPath = byName.keys.first(where: { $0.lowercased().hasSuffix(".opf") }),
              let opfData = byName[opfPath],
              let opfText = String(data: opfData, encoding: .utf8) else {
            throw ParserError.unsupportedEncoding  // 缺 OPF 视为无效 EPUB
        }

        let opfDir = (opfPath as NSString).deletingLastPathComponent

        // 通过 manifest 建立 id → href 映射，再读 spine 顺序
        let idToHref = extractManifestIdHref(from: opfText)
        let spineIds = extractSpineIdrefs(from: opfText)

        var chapters: [Chapter] = []
        // 按 spine 顺序
        for idref in spineIds {
            guard let href = idToHref[idref] else { continue }
            let resolved = resolve(href: href, baseDir: opfDir)
            guard let htmlData = byName[resolved],
                  let html = String(data: htmlData, encoding: .utf8) else { continue }
            let text = stripHtml(html)
            guard !text.isEmpty else { continue }
            chapters.append(Chapter(index: chapters.count, title: "", content: text))
        }

        // spine 解析不到则退而扫 manifest 中所有 XHTML
        if chapters.isEmpty {
            for href in idToHref.values {
                let resolved = resolve(href: href, baseDir: opfDir)
                guard let htmlData = byName[resolved],
                      let html = String(data: htmlData, encoding: .utf8) else { continue }
                let text = stripHtml(html)
                if !text.isEmpty {
                    chapters.append(Chapter(index: chapters.count, title: "", content: text))
                }
            }
        }

        guard !chapters.isEmpty else { throw ParserError.emptyFile }
        return ParsedBook(chapters: chapters)
    }

    // --- 内部工具（纯函数，便于测试） ---

    /// 从 OPF 抽出 manifest 的 id → href 映射
    func extractManifestIdHref(from opf: String) -> [String: String] {
        let pattern = #"<item[^>]*id=\"([^\"]+)\"[^>]*href=\"([^\"]+)\""#
        var result: [String: String] = [:]
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else { return result }
        let ns = opf as NSString
        for m in regex.matches(in: opf, options: [], range: NSRange(location: 0, length: ns.length)) {
            let id = ns.substring(with: m.range(at: 1))
            let href = ns.substring(with: m.range(at: 2))
            result[id] = href
        }
        return result
    }

    /// 从 OPF 抽出 spine 的 idref 顺序
    func extractSpineIdrefs(from opf: String) -> [String] {
        let pattern = #"<itemref[^>]*idref=\"([^\"]+)\""#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: []) else { return [] }
        let ns = opf as NSString
        return regex.matches(in: opf, options: [], range: NSRange(location: 0, length: ns.length))
            .map { ns.substring(with: $0.range(at: 1)) }
    }

    /// 抽 XHTML 纯文本（去标签，极简处理）
    func stripHtml(_ html: String) -> String {
        let noScript = html.replacingOccurrences(of: #"<script[\s\S]*?</script>"#,
                                                 with: "",
                                                 options: .regularExpression)
        let noTags = noScript.replacingOccurrences(of: #"<[^>]+>"#,
                                                   with: "\n",
                                                   options: .regularExpression)
        let entities: [String: String] = [
            "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
            "&quot;": "\"", "&#39;": "'"
        ]
        var out = noTags
        for (k, v) in entities { out = out.replacingOccurrences(of: k, with: v) }
        return out
            .components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .joined(separator: "\n")
    }

    private func resolve(href: String, baseDir: String) -> String {
        let clean = href.removingPercentEncoding ?? href
        if clean.hasPrefix("/") { return String(clean.dropFirst()) }
        if baseDir.isEmpty || baseDir == "." { return clean }
        return baseDir + "/" + clean
    }
}
