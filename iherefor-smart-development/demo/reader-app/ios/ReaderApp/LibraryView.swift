import SwiftUI
import UniformTypeIdentifiers

/// 书架视图：展示书籍列表 + 导入入口
struct LibraryView: View {
    @StateObject private var viewModel = LibraryViewModel(repository: InMemoryLibraryRepository())
    @State private var showImporter = false
    @State private var lastError: String?

    private static let allowedTypes: [UTType] = [
        UTType(filenameExtension: "epub") ?? .data,
        .pdf,
        .plainText
    ]

    var body: some View {
        NavigationStack {
            List {
                ForEach(viewModel.books()) { book in
                    NavigationLink {
                        ReaderView(book: book)
                    } label: {
                        VStack(alignment: .leading) {
                            Text(book.title)
                            Text("\(book.author ?? "未知作者") · \(book.format.rawValue)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .onDelete { indexSet in
                    for i in indexSet {
                        let book = viewModel.books()[i]
                        viewModel.removeBook(id: book.id)
                    }
                }
            }
            .navigationTitle("我的书架")
            .toolbar {
                Button {
                    showImporter = true
                } label: {
                    Image(systemName: "plus")
                }
            }
            .fileImporter(isPresented: $showImporter,
                          allowedContentTypes: Self.allowedTypes) { result in
                switch result {
                case .success(let url):
                    let ext = url.pathExtension
                    let secure = url.startAccessingSecurityScopedResource()
                    defer { if secure { url.stopAccessingSecurityScopedResource() } }
                    lastError = viewModel.importBook(ext: ext,
                                                     sourceUri: url.absoluteString,
                                                     title: url.deletingPathExtension().lastPathComponent)
                case .failure:
                    lastError = "导入失败"
                }
            }
            .alert("提示", isPresented: .constant(lastError != nil)) {
                Button("确定") { lastError = nil }
            } message: {
                Text(lastError ?? "")
            }
        }
    }
}
