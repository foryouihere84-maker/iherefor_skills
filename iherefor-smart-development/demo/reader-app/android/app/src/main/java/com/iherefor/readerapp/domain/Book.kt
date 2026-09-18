package com.iherefor.readerapp.domain

import java.util.Date

/** 书籍格式（共享契约，取值与 跨端共享层.md 一致） */
enum class BookFormat {
    EPUB, PDF, TXT;

    /** 该格式对应的进度定位类型 */
    val locatorType: LocatorType
        get() = when (this) {
            PDF -> LocatorType.PAGE
            EPUB, TXT -> LocatorType.CHAPTER
        }

    companion object {
        fun fromExtension(ext: String): BookFormat? = when (ext.lowercase().trim()) {
            "epub" -> EPUB
            "pdf" -> PDF
            "txt", "text" -> TXT
            else -> null
        }
    }
}

/** 进度定位类型（共享契约） */
enum class LocatorType { CHAPTER, PAGE }

/** 阅读进度 */
data class ReadingProgress(
    val bookId: String,
    val locatorType: LocatorType,
    val chapterIndex: Int? = null,
    val offset: Int? = null,
    val pageIndex: Int? = null,
    val updatedAt: Long = System.currentTimeMillis()
) {
    /** 越界回退到起点（第 0 章 / 第 0 页） */
    fun clamped(withinChapters: Int, withinPages: Int): ReadingProgress {
        return when (locatorType) {
            LocatorType.CHAPTER -> {
                val idx = chapterIndex ?: return this
                if (idx < 0 || idx >= withinChapters) copy(chapterIndex = 0) else this
            }
            LocatorType.PAGE -> {
                val idx = pageIndex ?: return this
                if (idx < 0 || idx >= withinPages) copy(pageIndex = 0) else this
            }
        }
    }
}

/** 书籍实体 */
data class Book(
    val id: String,
    val title: String,
    val author: String? = null,
    val format: BookFormat,
    val sourceUri: String,
    val coverUri: String? = null,
    val importedAt: Long = System.currentTimeMillis(),
    val progress: ReadingProgress? = null
)

/** 章节 */
data class Chapter(
    val index: Int,
    val title: String,
    val content: String
)

/** 解析结果：文档流（章节序列） */
data class ParsedBook(val chapters: List<Chapter>)
