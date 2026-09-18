package com.iherefor.readerapp.data

import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.domain.BookFormat
import com.iherefor.readerapp.domain.ReadingProgress
import com.iherefor.readerapp.domain.SharedRules
import java.util.UUID

/** 书架用例逻辑（依赖注入仓库） */
class LibraryViewModel(private val repository: LibraryRepository) {

    fun books(): List<Book> = repository.books()

    /** 导入一本书：格式校验 + sourceUri 去重。返回错误消息则拒绝导入。 */
    fun importBook(ext: String, sourceUri: String, title: String): String? {
        val format = BookFormat.fromExtension(ext) ?: return "不支持的格式"
        if (SharedRules.findDuplicate(sourceUri, repository.books()) != null) {
            return "已存在"
        }
        val book = Book(
            id = UUID.randomUUID().toString(),
            title = title,
            format = format,
            sourceUri = sourceUri
        )
        repository.add(book)
        return null
    }

    fun removeBook(id: String) { repository.remove(id) }

    fun saveProgress(bookId: String, progress: ReadingProgress) {
        val book = repository.books().firstOrNull { it.id == bookId } ?: return
        if (SharedRules.isProgressCompatible(book.format, progress)) {
            repository.updateProgress(bookId, progress)
        }
    }
}
