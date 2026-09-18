package com.iherefor.readerapp.data

import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.domain.ReadingProgress

/** 书架仓库接口（可测 seam） */
interface LibraryRepository {
    fun books(): List<Book>
    fun add(book: Book)
    fun remove(id: String)
    fun updateProgress(bookId: String, progress: ReadingProgress)
}

/** 内存实现，按 importedAt 降序 */
class InMemoryLibraryRepository : LibraryRepository {
    private val storage = mutableListOf<Book>()

    override fun books(): List<Book> = storage.sortedByDescending { it.importedAt }

    override fun add(book: Book) { storage.add(book) }

    override fun remove(id: String) { storage.removeAll { it.id == id } }

    override fun updateProgress(bookId: String, progress: ReadingProgress) {
        val idx = storage.indexOfFirst { it.id == bookId }
        if (idx >= 0) storage[idx] = storage[idx].copy(progress = progress)
    }
}
