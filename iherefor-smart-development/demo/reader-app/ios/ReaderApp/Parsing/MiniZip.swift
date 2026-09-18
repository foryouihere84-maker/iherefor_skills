import Foundation
import Compression

/// 极简 ZIP 读取器（只读，stored + deflate），避免引入第三方 ZIP 依赖。
/// EPUB 本质是 ZIP 容器，本章节 XHTML 通常 stored 或 deflate。
enum MiniZip {

    struct Entry {
        let name: String
        let data: Data
    }

    enum ZipError: Error { case invalid, unsupportedMethod }

    /// 解出所有 entry（名称 → 数据）
    static func unzip(data: Data) throws -> [Entry] {
        guard let eocd = findEOCD(data) else { throw ZipError.invalid }
        let (cdOffset, cdCount) = parseEOCD(data, eocd: eocd)

        var entries: [Entry] = []
        var cursor = cdOffset
        for _ in 0..<cdCount {
            guard readUInt32(data, at: cursor) == 0x02014B50 else { throw ZipError.invalid }
            let method = readUInt16(data, at: cursor + 10)
            let compSize = Int(readUInt32(data, at: cursor + 20))
            let nameLen = Int(readUInt16(data, at: cursor + 28))
            let extraLen = Int(readUInt16(data, at: cursor + 30))
            let commentLen = Int(readUInt16(data, at: cursor + 32))
            let localOffset = Int(readUInt32(data, at: cursor + 42))

            let nameStart = cursor + 46
            guard let name = String(data: data.subdata(in: nameStart..<nameStart + nameLen),
                                    encoding: .utf8) else {
                cursor = cursor + 46 + nameLen + extraLen + commentLen
                continue
            }

            // 读 local header
            guard readUInt32(data, at: localOffset) == 0x04034B50 else { throw ZipError.invalid }
            let lNameLen = Int(readUInt16(data, at: localOffset + 26))
            let lExtraLen = Int(readUInt16(data, at: localOffset + 28))
            let dataStart = localOffset + 30 + lNameLen + lExtraLen
            let raw = data.subdata(in: dataStart..<dataStart + compSize)

            let content: Data
            switch method {
            case 0:  // stored
                content = raw
            case 8:  // deflate
                content = try inflate(raw)
            default:
                content = try inflate(raw)  // 尝试 deflate 兜底
            }

            entries.append(Entry(name: name, data: content))
            cursor = cursor + 46 + nameLen + extraLen + commentLen
        }
        return entries
    }

    // --- helpers ---

    private static func findEOCD(_ data: Data) -> Int? {
        let sig: [UInt8] = [0x50, 0x4B, 0x05, 0x06]
        let n = data.count
        guard n >= 22 else { return nil }
        let searchLen = min(n, 65536 + 22)
        let lower = n - searchLen
        var i = n - 22
        while i >= lower {
            if data[i] == sig[0] && data[i+1] == sig[1] && data[i+2] == sig[2] && data[i+3] == sig[3] {
                return i
            }
            i -= 1
        }
        return nil
    }

    private static func parseEOCD(_ data: Data, eocd: Int) -> (cdOffset: Int, cdCount: Int) {
        let count = Int(readUInt16(data, at: eocd + 10))
        let offset = Int(readUInt32(data, at: eocd + 16))
        return (offset, count)
    }

    private static func readUInt16(_ data: Data, at i: Int) -> UInt16 {
        UInt16(data[i]) | (UInt16(data[i+1]) << 8)
    }

    private static func readUInt32(_ data: Data, at i: Int) -> UInt32 {
        UInt32(data[i]) | (UInt32(data[i+1]) << 8) | (UInt32(data[i+2]) << 16) | (UInt32(data[i+3]) << 24)
    }

    /// 用系统 Compression 解 deflate（zlib 头）
    private static func inflate(_ raw: Data) throws -> Data {
        // raw deflate 流可能带 zlib header；Compression 的 COMPRESSION_ZLIB 需要 zlib header
        try raw.withUnsafeBytes { src -> Data in
            let srcPtr = src.bindMemory(to: UInt8.self)
            guard let base = srcPtr.baseAddress else { throw ZipError.invalid }
            let dstCapacity = max(raw.count * 4, 1024)
            let dst = UnsafeMutablePointer<UInt8>.allocate(capacity: dstCapacity)
            defer { dst.deallocate() }
            let written = compression_decode_buffer(dst, dstCapacity, base, raw.count, nil, COMPRESSION_ZLIB)
            guard written > 0 else { throw ZipError.unsupportedMethod }
            return Data(bytes: dst, count: written)
        }
    }
}
