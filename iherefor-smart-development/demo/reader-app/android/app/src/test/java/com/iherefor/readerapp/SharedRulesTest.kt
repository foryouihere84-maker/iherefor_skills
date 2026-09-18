package com.iherefor.readerapp

import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.domain.BookFormat
import com.iherefor.readerapp.domain.LocatorType
import com.iherefor.readerapp.domain.ReadingProgress
import com.iherefor.readerapp.domain.SharedRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SharedRulesTest {

    @Test
    fun `shouldRejectUnsupportedFormat`() {
        assertNull(BookFormat.fromExtension("mobi"))
        assertNull(BookFormat.fromExtension("azw"))
        assertNull(BookFormat.fromExtension(""))
    }

    @Test
    fun `shouldRecognizeSupportedFormat`() {
        assertEquals(BookFormat.EPUB, BookFormat.fromExtension("epub"))
        assertEquals(BookFormat.PDF, BookFormat.fromExtension("PDF"))
        assertEquals(BookFormat.TXT, BookFormat.fromExtension("txt"))
    }

    @Test
    fun `shouldClassifyPdfAsPageLocator`() {
        assertEquals(LocatorType.PAGE, BookFormat.PDF.locatorType)
    }

    @Test
    fun `shouldClassifyEpubAndTxtAsChapterLocator`() {
        assertEquals(LocatorType.CHAPTER, BookFormat.EPUB.locatorType)
        assertEquals(LocatorType.CHAPTER, BookFormat.TXT.locatorType)
    }

    @Test
    fun `shouldClampProgressToStartOnOutOfRangePage`() {
        val p = ReadingProgress(bookId = "1", locatorType = LocatorType.PAGE, pageIndex = 99)
        assertEquals(0, p.clamped(withinChapters = 0, withinPages = 10).pageIndex)
    }

    @Test
    fun `shouldClampProgressToStartOnOutOfRangeChapter`() {
        val p = ReadingProgress(bookId = "1", locatorType = LocatorType.CHAPTER,
            chapterIndex = 50, offset = 3)
        assertEquals(0, p.clamped(withinChapters = 5, withinPages = 0).chapterIndex)
    }

    @Test
    fun `shouldKeepValidProgressIntact`() {
        val p = ReadingProgress(bookId = "1", locatorType = LocatorType.PAGE, pageIndex = 3)
        assertEquals(3, p.clamped(withinChapters = 0, withinPages = 10).pageIndex)
    }

    @Test
    fun `shouldDedupeBySourceUri`() {
        val a = Book(id = "1", title = "A", format = BookFormat.EPUB, sourceUri = "file:///a.epub")
        val b = Book(id = "2", title = "B", format = BookFormat.TXT, sourceUri = "file:///b.txt")
        assertEquals("1", SharedRules.findDuplicate("file:///a.epub", listOf(a, b))?.id)
        assertNull(SharedRules.findDuplicate("file:///c.epub", listOf(a, b)))
    }

    @Test
    fun `shouldVerifyProgressFormatCompatibility`() {
        val pageProgress = ReadingProgress(bookId = "1", locatorType = LocatorType.PAGE, pageIndex = 0)
        assertTrue(SharedRules.isProgressCompatible(BookFormat.PDF, pageProgress))
        assertFalse(SharedRules.isProgressCompatible(BookFormat.EPUB, pageProgress))

        val chapterProgress = ReadingProgress(bookId = "1", locatorType = LocatorType.CHAPTER,
            chapterIndex = 0, offset = 0)
        assertTrue(SharedRules.isProgressCompatible(BookFormat.TXT, chapterProgress))
        assertFalse(SharedRules.isProgressCompatible(BookFormat.PDF, chapterProgress))
    }
}
