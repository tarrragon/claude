/**
 * 匯入資料格式版本偵測
 *
 * 負責辨識匯入資料為 v1（category-based）或 v2（tag-based）格式，
 * 支援 JSON 和 CSV 兩種來源。
 *
 * 業務規則：偵測優先序定義於 feature-spec 2.2/2.3 節。
 */

// === JSON 版本偵測 ===

/**
 * 偵測匯入 JSON 資料的格式版本
 *
 * 偵測規則（依優先序）：
 * 1. metadata.formatVersion 以 "2." 開頭 -> v2
 * 2. 有 metadata 且 books 中任一物件含 readingStatus -> v2
 * 3. data 本身是陣列 -> v1
 * 4. data.books 是陣列但無 metadata.formatVersion -> v1
 * 5. 以上皆不符合 -> null
 *
 * @param {*} data - 解析後的 JSON 資料（物件或陣列）
 * @returns {'v1' | 'v2' | null} 格式版本，null 表示無法辨識
 */
function detectFormatVersion (data) {
  if (data === null || data === undefined || typeof data !== 'object') {
    return null
  }

  // 規則 1: metadata.formatVersion 以 "2." 開頭
  const formatVersion = data?.metadata?.formatVersion
  if (typeof formatVersion === 'string' && formatVersion.startsWith('2.')) {
    return 'v2'
  }

  // 規則 2: 有 metadata 且 books 中任一物件含 readingStatus
  if (data?.metadata && Array.isArray(data?.books)) {
    const hasReadingStatus = data.books.some(
      (book) => book && typeof book === 'object' && 'readingStatus' in book
    )
    if (hasReadingStatus) {
      return 'v2'
    }
  }

  // 規則 3: data 本身是陣列
  if (Array.isArray(data)) {
    return 'v1'
  }

  // 規則 4: data.books 是陣列但無 metadata.formatVersion
  if (Array.isArray(data?.books)) {
    return 'v1'
  }

  // 規則 5: 無法辨識
  return null
}

// === CSV 版本偵測 ===

/**
 * 偵測 CSV 匯入資料的格式版本
 *
 * 偵測規則：
 * - headers 含 'readingStatus' -> v2
 * - headers 含 'isNew' 或 'isFinished' -> v1
 * - 以上皆無 -> v1（降級處理）
 *
 * @param {string[]} headers - CSV 標題行欄位名稱陣列
 * @returns {'v1' | 'v2'} 格式版本（CSV 不回傳 null，預設降級為 v1）
 */
function detectCsvFormatVersion (headers) {
  if (!Array.isArray(headers)) {
    return 'v1'
  }

  if (headers.includes('readingStatus')) {
    return 'v2'
  }

  // isNew 或 isFinished 存在 -> v1（明確），否則也降級為 v1
  return 'v1'
}

// === 匯出 ===

module.exports = { detectFormatVersion, detectCsvFormatVersion }
