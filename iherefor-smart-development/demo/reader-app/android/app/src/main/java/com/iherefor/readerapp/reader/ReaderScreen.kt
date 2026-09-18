package com.iherefor.readerapp.reader

import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.domain.BookFormat
import com.iherefor.readerapp.domain.ParsedBook
import com.iherefor.readerapp.parsing.BookReaderService
import java.io.File

@Composable
fun ReaderScreen(book: Book) {
    when (book.format) {
        BookFormat.PDF -> PdfReaderScreen(book.sourceUri)
        BookFormat.EPUB, BookFormat.TXT -> ReflowReaderScreen(book)
    }
}

@Composable
fun ReflowReaderScreen(book: Book) {
    val context = LocalContext.current
    val service = remember { BookReaderService(context) }
    var parsedBook by remember { mutableStateOf<ParsedBook?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var index by remember { mutableStateOf(0) }

    LaunchedEffect(book.id) {
        runCatching { service.readAndParse(book) }
            .onSuccess { parsedBook = it }
            .onFailure { error = "解析失败：${it.message}" }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        when {
            error != null -> Text(error!!, color = MaterialTheme.colorScheme.onSurfaceVariant)
            parsedBook == null -> Text("解析中…")
            parsedBook!!.chapters.isEmpty() -> Text("暂无内容")
            else -> {
                val chapters = parsedBook!!.chapters
                val idx = index.coerceIn(0, chapters.size - 1)
                Text(
                    text = chapters[idx].content,
                    modifier = Modifier.weight(1f).verticalScroll(rememberScrollState())
                )
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Button(onClick = { if (index > 0) index-- }, enabled = index > 0) {
                        Text("上一章")
                    }
                    Text("${idx + 1} / ${chapters.size}")
                    Button(
                        onClick = { if (index < chapters.size - 1) index++ },
                        enabled = index < chapters.size - 1
                    ) { Text("下一章") }
                }
            }
        }
    }
}

@Composable
fun PdfReaderScreen(sourceUri: String) {
    var pageIndex by remember { mutableStateOf(0) }
    var totalPages by remember { mutableStateOf(0) }
    var bitmap by remember { mutableStateOf<android.graphics.Bitmap?>(null) }

    LaunchedEffect(sourceUri, pageIndex) {
        runCatching {
            val path = sourceUri.removePrefix("file://")
            val pfd = ParcelFileDescriptor.open(File(path), ParcelFileDescriptor.MODE_READ_ONLY)
            val renderer = PdfRenderer(pfd)
            totalPages = renderer.pageCount
            val page = renderer.openPage(pageIndex.coerceIn(0, renderer.pageCount - 1))
            val bmp = android.graphics.Bitmap.createBitmap(page.width, page.height,
                android.graphics.Bitmap.Config.ARGB_8888)
            page.render(bmp, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            page.close()
            renderer.close()
            pfd.close()
            bitmap = bmp
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        val bmp = bitmap
        if (bmp != null) {
            Image(
                bitmap = bmp.asImageBitmap(),
                contentDescription = "PDF 页",
                modifier = Modifier.weight(1f)
            )
        } else {
            Text("正在加载 PDF…")
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Button(onClick = { if (pageIndex > 0) pageIndex-- }, enabled = pageIndex > 0) {
                Text("上一页")
            }
            Text("${pageIndex + 1} / $totalPages")
            Button(onClick = { if (pageIndex < totalPages - 1) pageIndex++ },
                enabled = pageIndex < totalPages - 1) {
                Text("下一页")
            }
        }
    }
}
