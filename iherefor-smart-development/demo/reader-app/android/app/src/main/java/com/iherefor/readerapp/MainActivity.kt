package com.iherefor.readerapp

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.iherefor.readerapp.data.InMemoryLibraryRepository
import com.iherefor.readerapp.data.LibraryViewModel
import com.iherefor.readerapp.domain.Book
import com.iherefor.readerapp.reader.ReaderScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            LibraryScreen()
        }
    }
}

@Composable
fun LibraryScreen() {
    val viewModel = remember { LibraryViewModel(InMemoryLibraryRepository()) }
    var books by remember { mutableStateOf(viewModel.books()) }
    var openBook by remember { mutableStateOf<Book?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            val ext = uri.lastPathSegment?.substringAfterLast('.', "") ?: ""
            val title = uri.lastPathSegment?.substringAfterLast('/', "")?.substringBeforeLast('.') ?: "未命名"
            val err = viewModel.importBook(ext, uri.toString(), title)
            if (err != null) error = err
            books = viewModel.books()
        }
    }

    openBook?.let { book ->
        BackHandler { openBook = null }
        ReaderScreen(book = book)
    } ?: run {
        LazyColumn(Modifier.fillMaxSize()) {
            item {
                Text("我的书架", style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.padding(16.dp))
            }
            items(books, key = { it.id }) { book ->
                Card(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)
                    .clickable { openBook = book }) {
                    Column(Modifier.padding(16.dp)) {
                        Text(book.title)
                        Text(
                            "${book.author ?: "未知作者"} · ${book.format.name}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
            item {
                Button(onClick = {
                    launcher.launch(arrayOf("*/*"))
                }, modifier = Modifier.padding(16.dp)) {
                    Text("+ 导入书籍")
                }
            }
        }
    }

    error?.let {
        AlertDialog(
            onDismissRequest = { error = null },
            confirmButton = { TextButton(onClick = { error = null }) { Text("确定") } },
            title = { Text("提示") },
            text = { Text(it) }
        )
    }
}
