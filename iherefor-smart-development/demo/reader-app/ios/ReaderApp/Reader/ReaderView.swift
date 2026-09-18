import SwiftUI
import PDFKit

/// 阅读器视图：按格式分派渲染（重排文本 / PDF 按页）。
/// 打开时通过 BookReaderService 解析真实内容（不再硬编码空内容）。
struct ReaderView: View {
    let book: Book
    private let service = BookReaderService()

    var body: some View {
        switch book.format {
        case .pdf:
            PDFReaderView(url: URL(string: book.sourceUri))
        case .epub, .txt:
            ReflowReaderView(book: book, service: service)
        }
    }
}

/// 重排文本阅读（EPUB/TXT）：打开时解析章节并渲染
struct ReflowReaderView: View {
    let book: Book
    let service: BookReaderService
    @State private var parsedBook: ParsedBook?
    @State private var loadError: String?
    @State private var index = 0

    var body: some View {
        Group {
            if let loadError {
                Text(loadError).foregroundColor(.secondary)
            } else if let parsedBook, !parsedBook.chapters.isEmpty {
                chapterContent(parsedBook.chapters)
            } else if parsedBook != nil {
                Text("暂无内容")
            } else {
                ProgressView("解析中…")
            }
        }
        .navigationTitle(book.title)
        .onAppear { load() }
    }

    @ViewBuilder
    private func chapterContent(_ chapters: [Chapter]) -> some View {
        VStack {
            ScrollView {
                Text(chapters[index].content)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack {
                Button("上一章") { if index > 0 { index -= 1 } }
                    .disabled(index == 0)
                Spacer()
                Text("\(index + 1) / \(chapters.count)")
                Spacer()
                Button("下一章") { if index < chapters.count - 1 { index += 1 } }
                    .disabled(index >= chapters.count - 1)
            }
            .padding()
        }
    }

    private func load() {
        do {
            parsedBook = try service.readAndParse(book: book)
        } catch {
            loadError = "解析失败：\(error.localizedDescription)"
        }
    }
}

/// PDF 按页渲染（系统 PDFKit）
struct PDFReaderView: View {
    let url: URL?
    @State private var document: PDFDocument?

    var body: some View {
        Group {
            if let url, let doc = PDFDocument(url: url) {
                PDFKitView(document: doc)
            } else {
                Text("无法打开 PDF")
            }
        }
        .navigationTitle("PDF")
    }
}

struct PDFKitView: UIViewRepresentable {
    let document: PDFDocument

    func makeUIView(context: Context) -> PDFView {
        let view = PDFView()
        view.document = document
        view.autoScales = true
        view.displayMode = .singlePage
        view.displayDirection = .horizontal
        return view
    }

    func updateUIView(_ uiView: PDFView, context: Context) {}
}
