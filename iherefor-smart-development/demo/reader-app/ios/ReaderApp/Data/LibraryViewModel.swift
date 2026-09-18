import Foundation

/// 书架 ViewModel：承载导入、去重、删除等用例逻辑（依赖注入仓库）
final class LibraryViewModel: ObservableObject {

    private let repository: LibraryRepository

    init(repository: LibraryRepository) {
        self.repository = repository
    }

    func books() -> [Book] {
        repository.books()
    }

    /// 导入一本书：格式校验 + sourceUri 去重。返回错误则拒绝导入。
    @discardableResult
    func importBook(ext: String, sourceUri: String, title: String) -> String? {
        guard let format = SharedRules.detectFormat(fromExtension: ext) else {
            return "不支持的格式"
        }
        if let dup = SharedRules.findDuplicate(sourceUri: sourceUri, in: repository.books()) {
            return dup.id == "" ? nil : "已存在"  // 去重，不重复添加
        }
        let book = Book(id: UUID().uuidString, title: title, author: nil,
                        format: format, sourceUri: sourceUri, coverUri: nil,
                        importedAt: Date(), progress: nil)
        repository.add(book)
        return nil
    }

    func removeBook(id: String) {
        repository.remove(id: id)
    }

    func saveProgress(bookId: String, progress: ReadingProgress) {
        guard let book = repository.books().first(where: { $0.id == bookId }) else { return }
        guard SharedRules.isProgressCompatible(format: book.format, progress: progress) else { return }
        repository.updateProgress(bookId: bookId, progress: progress)
    }
}
