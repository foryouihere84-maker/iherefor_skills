package com.iherefor.readerapp.parsing

import com.iherefor.readerapp.domain.Chapter
import com.iherefor.readerapp.domain.ParsedBook
import java.nio.charset.Charset

/** TXT 解析器：按空行切分章节，UTF-8 优先、GBK 兜底 */
class TxtParser : BookParser {

    override fun parse(data: ByteArray): ParsedBook {
        if (data.isEmpty()) throw ParserException("文件为空")
        val text = decode(data)
        val chapters = splitChapters(text)
        if (chapters.isEmpty()) throw ParserException("文件为空")
        return ParsedBook(chapters)
    }

    fun decode(data: ByteArray): String = try {
        String(data, Charsets.UTF_8)
    } catch (e: Exception) {
        String(data, Charset.forName("GB18030"))
    }

    fun splitChapters(text: String): List<Chapter> {
        val normalized = text.replace("\r\n", "\n")
        val blocks = normalized.split("\n\n")
            .map { it.trim() }
            .filter { it.isNotEmpty() }

        if (blocks.isEmpty()) {
            val trimmed = normalized.trim()
            return if (trimmed.isEmpty()) emptyList()
            else listOf(Chapter(0, "", trimmed))
        }

        return blocks.mapIndexed { i, content ->
            val lines = content.split("\n", limit = 2)
            val title = if (lines.size > 1) lines[0] else ""
            Chapter(i, title, content)
        }
    }
}
