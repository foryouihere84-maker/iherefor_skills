package com.iherefor.readerapp.parsing

import com.iherefor.readerapp.domain.Chapter
import com.iherefor.readerapp.domain.ParsedBook

/** 自研最小 EPUB 解析器：解 ZIP → 找 OPF → 抽章节 XHTML 纯文本。 */
class EpubParser : BookParser {

    override fun parse(data: ByteArray): ParsedBook {
        if (data.isEmpty()) throw ParserException("文件为空")
        val entries = MiniZip.unzip(data)
        val byName = entries.associate { it.name.trimStart('/') to it.data }

        val opfPath = byName.keys.firstOrNull { it.lowercase().endsWith(".opf") }
            ?: throw ParserException("缺少 OPF")
        val opfText = String(byName[opfPath]!!, Charsets.UTF_8)

        val opfDir = opfPath.substringBeforeLast('/', "")

        val idToHref = extractManifestIdHref(opfText)
        val spineIds = extractSpineIdrefs(opfText)

        val chapters = mutableListOf<Chapter>()
        for (idref in spineIds) {
            val href = idToHref[idref] ?: continue
            val resolved = resolve(href, opfDir)
            val htmlData = byName[resolved] ?: continue
            val text = stripHtml(String(htmlData, Charsets.UTF_8))
            if (text.isNotEmpty()) {
                chapters.add(Chapter(chapters.size, "", text))
            }
        }

        if (chapters.isEmpty()) {
            for (href in idToHref.values) {
                val resolved = resolve(href, opfDir)
                val htmlData = byName[resolved] ?: continue
                val text = stripHtml(String(htmlData, Charsets.UTF_8))
                if (text.isNotEmpty()) {
                    chapters.add(Chapter(chapters.size, "", text))
                }
            }
        }

        if (chapters.isEmpty()) throw ParserException("无内容")
        return ParsedBook(chapters)
    }

    fun extractManifestIdHref(opf: String): Map<String, String> {
        val result = mutableMapOf<String, String>()
        val itemRegex = Regex("<item[^>]*id=\"([^\"]+)\"[^>]*href=\"([^\"]+)\"")
        for (m in itemRegex.findAll(opf)) {
            result[m.groupValues[1]] = m.groupValues[2]
        }
        return result
    }

    fun extractSpineIdrefs(opf: String): List<String> {
        val idrefRegex = Regex("<itemref[^>]*idref=\"([^\"]+)\"")
        return idrefRegex.findAll(opf).map { it.groupValues[1] }.toList()
    }

    fun stripHtml(html: String): String {
        var noScript = html.replace(Regex("<script[\\s\\S]*?</script>"), "")
        noScript = noScript.replace(Regex("<[^>]+>"), "\n")
        val entities = mapOf(
            "&nbsp;" to " ", "&amp;" to "&", "&lt;" to "<",
            "&gt;" to ">", "&quot;" to "\"", "&#39;" to "'"
        )
        var out = noScript
        for ((k, v) in entities) out = out.replace(k, v)
        return out.split("\n").map { it.trim() }.filter { it.isNotEmpty() }.joinToString("\n")
    }

    private fun resolve(href: String, baseDir: String): String {
        val clean = href
        if (clean.startsWith("/")) return clean.removePrefix("/")
        if (baseDir.isEmpty() || baseDir == ".") return clean
        return "$baseDir/$clean"
    }
}
