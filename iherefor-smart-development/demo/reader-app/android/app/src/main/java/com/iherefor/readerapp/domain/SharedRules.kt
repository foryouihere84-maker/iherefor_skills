package com.iherefor.readerapp.domain

/** 共享纯函数领域规则（跨端一致语义） */
object SharedRules {

    /** 是否支持该格式 */
    fun isSupported(format: BookFormat): Boolean = true  // 三值枚举天然全支持

    /** 进度↔格式兼容校验（共享不变量 #4） */
    fun isProgressCompatible(format: BookFormat, progress: ReadingProgress): Boolean =
        when (format) {
            BookFormat.PDF -> progress.locatorType == LocatorType.PAGE
            BookFormat.EPUB, BookFormat.TXT -> progress.locatorType == LocatorType.CHAPTER
        }

    /** 按 sourceUri 去重（共享不变量 #6）：返回已有书，若不存在 */
    fun findDuplicate(sourceUri: String, books: List<Book>): Book? =
        books.firstOrNull { it.sourceUri == sourceUri }
}
