import Foundation

/// 书架仓库协议（可测 seam）
protocol LibraryRepository {
    func books() -> [Book]
    func add(_ book: Book)
    func remove(id: String)
    func updateProgress(bookId: String, progress: ReadingProgress)
}

/// 内存实现（测试与演示用），按 importedAt 降序返回
final class InMemoryLibraryRepository: LibraryRepository {
    private var storage: [Book] = []

    func books() -> [Book] {
        storage.sorted { $0.importedAt > $1.importedAt }
    }

    func add(_ book: Book) {
        storage.append(book)
    }

    func remove(id: String) {
        storage.removeAll { $0.id == id }
    }

    func updateProgress(bookId: String, progress: ReadingProgress) {
        guard let idx = storage.firstIndex(where: { $0.id == bookId }) else { return }
        storage[idx].progress = progress
    }
}
