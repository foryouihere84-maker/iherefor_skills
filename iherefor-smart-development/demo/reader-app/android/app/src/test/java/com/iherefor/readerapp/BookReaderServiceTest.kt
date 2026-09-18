package com.iherefor.readerapp

import com.iherefor.readerapp.domain.BookFormat
import com.iherefor.readerapp.parsing.BookReaderService
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class BookReaderServiceTest {

    @Test
    fun `shouldDispatchTxtToTxtParser`() {
        val txt = "第一章\n内容AA\n\n第二章\n内容BB"
        val parsed = BookReaderService.parse(BookFormat.TXT, txt.toByteArray(Charsets.UTF_8))
        assertEquals(2, parsed.chapters.size)
        assertTrue(parsed.chapters[0].content.contains("内容AA"))
    }

    @Test
    fun `shouldDispatchEpubToEpubParser`() {
        val epub = makeEpub(
            "ch1.xhtml" to "<html><body><p>第一章 正文</p></body></html>",
            "ch2.xhtml" to "<html><body><p>第二章 正文</p></body></html>"
        )
        val parsed = BookReaderService.parse(BookFormat.EPUB, epub)
        assertEquals(2, parsed.chapters.size)
        assertTrue(parsed.chapters[0].content.contains("第一章 正文"))
    }

    @Test
    fun `shouldThrowForPdf`() {
        assertThrows(Exception::class.java) {
            BookReaderService.parse(BookFormat.PDF, "%PDF-1.4".toByteArray())
        }
    }

    private fun makeEpub(vararg chapters: Pair<String, String>): ByteArray {
        val opf = """
        <?xml version="1.0"?>
        <package xmlns="http://www.idpf.org/2007/opf" version="2.0">
          <manifest>
            <item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
            <item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
          </manifest>
          <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
        </package>
        """
        val baos = ByteArrayOutputStream()
        ZipOutputStream(baos).use { z ->
            z.putNextEntry(ZipEntry("mimetype"))
            z.write("application/epub+zip".toByteArray())
            z.closeEntry()
            z.putNextEntry(ZipEntry("OEBPS/content.opf"))
            z.write(opf.toByteArray())
            z.closeEntry()
            for ((name, body) in chapters) {
                z.putNextEntry(ZipEntry("OEBPS/$name"))
                z.write(body.toByteArray())
                z.closeEntry()
            }
        }
        return baos.toByteArray()
    }
}
