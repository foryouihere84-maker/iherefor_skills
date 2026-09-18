package com.iherefor.readerapp

import com.iherefor.readerapp.parsing.EpubParser
import com.iherefor.readerapp.parsing.ParserException
import com.iherefor.readerapp.parsing.TxtParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class TxtParserTest {

    @Test
    fun `shouldSplitTxtIntoChapters`() {
        val text = "第一章\n内容AA\n\n第二章\n内容BB\n\n第三章\n内容CC"
        val chapters = TxtParser().splitChapters(text)
        assertEquals(3, chapters.size)
        assertEquals(0, chapters[0].index)
        assertTrue(chapters[0].content.contains("内容AA"))
    }

    @Test
    fun `shouldSingleBlockBeOneChapter`() {
        val chapters = TxtParser().splitChapters("没有空行的整篇内容")
        assertEquals(1, chapters.size)
    }

    @Test
    fun `shouldEmptyTextYieldNoChapters`() {
        assertTrue(TxtParser().splitChapters("").isEmpty())
        assertTrue(TxtParser().splitChapters("  \n  ").isEmpty())
    }

    @Test
    fun `shouldRejectEmptyFile`() {
        assertThrows(ParserException::class.java) { TxtParser().parse(ByteArray(0)) }
    }

    @Test
    fun `shouldDecodeUtf8`() {
        assertEquals("你好", TxtParser().decode("你好".toByteArray(Charsets.UTF_8)))
    }
}

class EpubParserTest {

    @Test
    fun `shouldExtractManifestIdHref`() {
        val opf = "<manifest><item id=\"c1\" href=\"c1.xhtml\" media-type=\"application/xhtml+xml\"/>" +
                "<item id=\"c2\" href=\"ch2.html\"/></manifest>"
        val map = EpubParser().extractManifestIdHref(opf)
        assertEquals("c1.xhtml", map["c1"])
        assertEquals("ch2.html", map["c2"])
    }

    @Test
    fun `shouldExtractSpineIdrefsOrder`() {
        val opf = "<spine><itemref idref=\"c2\"/><itemref idref=\"c1\"/></spine>"
        assertEquals(listOf("c2", "c1"), EpubParser().extractSpineIdrefs(opf))
    }

    @Test
    fun `shouldStripHtml`() {
        val html = "<html><body><p>你好 &amp; 世界</p><script>var x=1;</script></body></html>"
        val text = EpubParser().stripHtml(html)
        assertTrue(text.contains("你好 & 世界"))
        assertTrue(!text.contains("<p>"))
        assertTrue(!text.contains("var x"))
    }

    @Test
    fun `shouldRejectEmptyFile`() {
        assertThrows(ParserException::class.java) { EpubParser().parse(ByteArray(0)) }
    }

    @Test
    fun `shouldRejectInvalidZip`() {
        assertThrows(Exception::class.java) {
            EpubParser().parse(byteArrayOf(0x00, 0x01, 0x02))
        }
    }
}
