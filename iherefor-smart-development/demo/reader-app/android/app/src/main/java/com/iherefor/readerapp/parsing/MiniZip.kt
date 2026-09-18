package com.iherefor.readerapp.parsing

import java.io.ByteArrayInputStream
import java.util.zip.ZipInputStream

/** 极简 ZIP 读取（stored + deflate），避免第三方依赖。 */
object MiniZip {

    data class Entry(val name: String, val data: ByteArray)

    fun unzip(data: ByteArray): List<Entry> {
        val entries = mutableListOf<Entry>()
        ZipInputStream(ByteArrayInputStream(data)).use { zis ->
            var entry = zis.nextEntry
            while (entry != null) {
                if (!entry.isDirectory) {
                    val buf = zis.readBytes()
                    entries.add(Entry(entry.name, buf))
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }
        return entries
    }
}
