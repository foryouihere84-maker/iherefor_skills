package com.iherefor.readerapp.parsing

import com.iherefor.readerapp.domain.ParsedBook

/** 可替换解析 seam（对齐 跨端共享层契约，未来可换 Readium） */
interface BookParser {
    fun parse(data: ByteArray): ParsedBook
}

class ParserException(message: String) : Exception(message)
