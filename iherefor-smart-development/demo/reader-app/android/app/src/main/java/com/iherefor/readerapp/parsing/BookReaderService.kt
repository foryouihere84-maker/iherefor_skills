package com.iherefor.readerapp.parsing

import android.content.Context
import android.net.Uri
import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.domain.BookFormat
import com.iherefor.readerapp.domain.ParsedBook

/** 按格式分派的读取服务：读源文件字节 → 选 parser → 解析出文档流（可测 seam 在 parser 工厂） */
class BookReaderService(private val context: Context) {

    companion object {
        /** 纯函数式分派：不依赖 Context，可直接单测 */
        fun parse(format: BookFormat, data: ByteArray): ParsedBook {
            val parser = when (format) {
                BookFormat.EPUB -> EpubParser()
                BookFormat.TXT -> TxtParser()
                BookFormat.PDF -> throw ParserException("PDF 非重排格式")
            }
            return parser.parse(data)
        }
    }

    /** 从源 URI 读取并解析 */
    fun readAndParse(book: Book): ParsedBook {
        if (book.format == BookFormat.PDF) throw ParserException("PDF 非重排格式")
        val bytes = readBytes(book.sourceUri)
        return parse(book.format, bytes)
    }

    private fun readBytes(sourceUri: String): ByteArray {
        val uri = Uri.parse(sourceUri)
        return context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw ParserException("无法读取文件")
    }
}
