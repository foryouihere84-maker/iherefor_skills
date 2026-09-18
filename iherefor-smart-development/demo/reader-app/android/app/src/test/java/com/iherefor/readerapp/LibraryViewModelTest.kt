package com.iherefor.readerapp

import com.iherefor.readerapp.data.InMemoryLibraryRepository
import com.iherefor.readerapp.data.LibraryViewModel
import com.iherefor.readerapp.domain.LocatorType
import com.iherefor.readerapp.domain.ReadingProgress
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LibraryViewModelTest {

    private val repo = InMemoryLibraryRepository()
    private val vm = LibraryViewModel(repo)

    @Test
    fun `shouldRejectUnsupportedFormatAtVmLevel`() {
        assertEquals("不支持的格式", vm.importBook("mobi", "file:///a.mobi", "A"))
        assertEquals(0, vm.books().size)
    }

    @Test
    fun `shouldDedupeBySourceUri`() {
        assertNull(vm.importBook("epub", "file:///a.epub", "A"))
        assertEquals("已存在", vm.importBook("epub", "file:///a.epub", "A2"))
        assertEquals(1, vm.books().size)
    }

    @Test
    fun `shouldImportAddBook`() {
        assertNull(vm.importBook("txt", "file:///b.txt", "B"))
        assertEquals(1, vm.books().size)
    }

    @Test
    fun `shouldRemoveBookRemovesRecord`() {
        vm.importBook("pdf", "file:///c.pdf", "C")
        val id = vm.books().first().id
        vm.removeBook(id)
        assertEquals(0, vm.books().size)
    }

    @Test
    fun `shouldSaveIncompatibleProgressIsIgnored`() {
        vm.importBook("pdf", "file:///c.pdf", "C")
        val id = vm.books().first().id
        val chapterProgress = ReadingProgress(bookId = id, locatorType = LocatorType.CHAPTER,
            chapterIndex = 0, offset = 0)
        vm.saveProgress(id, chapterProgress)
        assertNull(vm.books().first().progress)
    }
}
