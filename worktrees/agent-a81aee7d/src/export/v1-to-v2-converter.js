/**
 * v1 -> v2 匯入資料轉換器
 *
 * 將 v1（category-based）格式的書籍資料轉換為 v2（tag-based）格式。
 * 純轉換邏輯，不涉及 Storage 寫入。
 *
 * 業務規則：
 * - readingStatus 轉換重用 BookSchemaV2.mapV1StatusToV2
 * - progress 正規化重用 BookSchemaV2.normalizeV1Progress
 * - category -> tag 轉換由 convertV1CategoryToTag 處理
 */

const BookSchemaV2 = require('../data-management/BookSchemaV2')
const { BookValidationError } = require('../core/errors/BookValidationError')

// === 常數 ===

const IMPORTED_CATEGORY_ID = 'cat_imported'
const IMPORTED_CATEGORY_NAME = '匯入分類'
const TAG_ID_RANDOM_LENGTH = 6
const DEFAULT_SOURCE = 'readmoo'
const EXPORT_SOURCE_NAME = 'readmoo-book-extractor'
const FORMAT_VERSION = '2.0.0'
const PROGRESS_MIN = 0
const PROGRESS_MAX = 100
const SKIP_CATEGORIES = ['', '未分類']

// === 單本書籍轉換 ===

/**
 * 將單本 v1 書籍轉換為 v2 格式
 *
 * 業務規則：
 * - author (string) -> authors (string[])
 * - isNew/isFinished/progress -> readingStatus（重用 BookSchemaV2.mapV1StatusToV2）
 * - progress 正規化 + clamp(0, 100)
 * - category 保留為 _v1Category 暫存欄位
 * - 轉換後不含 isNew、isFinished、category
 *
 * @param {Object} v1Book - v1 格式書籍物件
 * @param {string} [importTimestamp] - 匯入時間 ISO 字串
 * @returns {Object} v2 格式書籍物件
 * @throws {BookValidationError} 輸入為 null 或缺少必填欄位時
 */
function convertV1ToV2Book (v1Book, importTimestamp) {
  if (!v1Book || typeof v1Book !== 'object') {
    throw BookValidationError.create(
      { id: 'unknown', title: 'unknown' },
      '輸入必須為物件'
    )
  }

  const missingFields = []
  if (!v1Book.id) missingFields.push('id')
  if (!v1Book.title) missingFields.push('title')

  if (missingFields.length > 0) {
    throw BookValidationError.missingFields(v1Book, missingFields)
  }

  const timestamp = importTimestamp || new Date().toISOString()

  // progress 正規化 + clamp
  const normalizedProgress = clampProgress(
    BookSchemaV2.normalizeV1Progress(v1Book.progress)
  )

  // author -> authors 轉換
  const authors = convertAuthorToAuthors(v1Book.author)

  const v2Book = {
    id: v1Book.id,
    title: v1Book.title,
    authors,
    publisher: v1Book.publisher || '',
    readingStatus: BookSchemaV2.mapV1StatusToV2(v1Book),
    progress: normalizedProgress,
    type: v1Book.type || '',
    cover: v1Book.cover || '',
    tagIds: [],
    isManualStatus: false,
    extractedAt: v1Book.extractedAt || timestamp,
    updatedAt: timestamp,
    source: DEFAULT_SOURCE
  }

  // category 保留為暫存欄位供上層使用
  if (v1Book.category !== undefined && v1Book.category !== null) {
    v2Book._v1Category = v1Book.category
  }

  return v2Book
}

/**
 * 將 v1 author 字串轉換為 v2 authors 陣列
 *
 * @param {*} author - v1 的 author 欄位值
 * @returns {string[]} authors 陣列
 */
function convertAuthorToAuthors (author) {
  if (!author || typeof author !== 'string' || author.trim() === '') {
    return []
  }
  return [author]
}

/**
 * 將 progress 值限制在 0-100 範圍內
 *
 * @param {number} progress - 正規化後的 progress 值
 * @returns {number} clamp 後的值
 */
function clampProgress (progress) {
  if (progress < PROGRESS_MIN) return PROGRESS_MIN
  if (progress > PROGRESS_MAX) return PROGRESS_MAX
  return progress
}

// === Category -> Tag 轉換 ===

/**
 * 將 v1 的 category 字串集合轉換為 tag 結構
 *
 * 業務規則：
 * - 跳過空字串和「未分類」
 * - 空輸入回傳 tagCategory: null
 * - 正常輸入建立「匯入分類」TagCategory + 每個 category 一個 Tag
 *
 * @param {string[]} categories - 不重複的 category 名稱陣列
 * @param {string} [timestamp] - 建立時間 ISO 字串
 * @returns {{ tagCategory: Object|null, tags: Object[], categoryToTagIdMap: Map<string, string> }}
 */
function convertV1CategoryToTag (categories, timestamp) {
  const emptyResult = {
    tagCategory: null,
    tags: [],
    categoryToTagIdMap: new Map()
  }

  if (!Array.isArray(categories)) {
    return emptyResult
  }

  // 過濾空字串和「未分類」
  const validCategories = categories.filter(
    (cat) => typeof cat === 'string' && !SKIP_CATEGORIES.includes(cat.trim())
  )

  if (validCategories.length === 0) {
    return emptyResult
  }

  const ts = timestamp || new Date().toISOString()

  // 建立「匯入分類」TagCategory
  const tagCategory = {
    id: IMPORTED_CATEGORY_ID,
    name: IMPORTED_CATEGORY_NAME,
    description: '',
    color: '#808080',
    isSystem: false,
    sortOrder: 0,
    createdAt: ts,
    updatedAt: ts
  }

  const tags = []
  const categoryToTagIdMap = new Map()

  for (const categoryName of validCategories) {
    const tagId = generateTagId()
    const tag = {
      id: tagId,
      name: categoryName,
      categoryId: IMPORTED_CATEGORY_ID,
      isSystem: false,
      sortOrder: 0,
      createdAt: ts,
      updatedAt: ts
    }
    tags.push(tag)
    categoryToTagIdMap.set(categoryName, tagId)
  }

  return { tagCategory, tags, categoryToTagIdMap }
}

/**
 * 產生 Tag ID
 * 格式：tag_{timestamp_ms}-{隨機6碼}
 *
 * @returns {string} Tag ID
 */
function generateTagId () {
  const timestampMs = Date.now()
  const randomPart = Math.random().toString(36).substring(2, 2 + TAG_ID_RANDOM_LENGTH)
  return `tag_${timestampMs}-${randomPart}`
}

// === 完整資料轉換 ===

/**
 * 完整的 v1 -> v2 資料轉換（組合函式的頂層 API）
 *
 * 處理流程：
 * 1. 提取書籍陣列
 * 2. 逐本呼叫 convertV1ToV2Book
 * 3. 收集所有 _v1Category（去重、過濾）
 * 4. 呼叫 convertV1CategoryToTag 建立 tag 結構
 * 5. 根據 categoryToTagIdMap 將 tagId 寫入書籍的 tagIds
 * 6. 移除 _v1Category 暫存欄位
 * 7. 組裝 v2 interchange format
 *
 * @param {Object|Array} v1Data - v1 格式的匯入資料
 * @returns {Object} v2 interchange format 結構
 */
function convertV1ToV2Data (v1Data) {
  const importTimestamp = new Date().toISOString()

  // 步驟 1: 提取書籍陣列
  const v1Books = extractBooksArray(v1Data)

  // 步驟 2: 逐本轉換（單本失敗不中斷）
  const convertedBooks = []
  for (const v1Book of v1Books) {
    try {
      const v2Book = convertV1ToV2Book(v1Book, importTimestamp)
      convertedBooks.push(v2Book)
    } catch (error) {
      // 單本書轉換失敗，跳過該書，繼續其他書籍
      // 靜默原因：匯入流程容錯設計，單本失敗不應中斷整批匯入
    }
  }

  // 步驟 3: 收集所有 _v1Category（去重）
  const categorySet = new Set()
  for (const book of convertedBooks) {
    if (book._v1Category && typeof book._v1Category === 'string') {
      categorySet.add(book._v1Category)
    }
  }
  const uniqueCategories = Array.from(categorySet)

  // 步驟 4: 建立 tag 結構
  const { tagCategory, tags, categoryToTagIdMap } =
    convertV1CategoryToTag(uniqueCategories, importTimestamp)

  // 步驟 5: 將 tagId 寫入書籍的 tagIds
  for (const book of convertedBooks) {
    if (book._v1Category && categoryToTagIdMap.has(book._v1Category)) {
      book.tagIds = [categoryToTagIdMap.get(book._v1Category)]
    }
  }

  // 步驟 6: 移除 _v1Category 暫存欄位
  for (const book of convertedBooks) {
    delete book._v1Category
  }

  // 步驟 7: 組裝 v2 interchange format
  const tagCategories = tagCategory ? [tagCategory] : []

  return {
    metadata: {
      formatVersion: FORMAT_VERSION,
      exportDate: importTimestamp,
      source: EXPORT_SOURCE_NAME,
      schemaVersion: BookSchemaV2.SCHEMA_VERSION,
      totalBooks: convertedBooks.length,
      totalTags: tags.length,
      totalTagCategories: tagCategories.length
    },
    tagCategories,
    tags,
    books: convertedBooks
  }
}

/**
 * 從 v1 資料中提取書籍陣列
 *
 * @param {Object|Array} v1Data - v1 格式資料
 * @returns {Array} 書籍陣列
 */
function extractBooksArray (v1Data) {
  if (Array.isArray(v1Data)) {
    return v1Data
  }
  if (v1Data && Array.isArray(v1Data.books)) {
    return v1Data.books
  }
  return []
}

// === 匯出 ===

module.exports = {
  convertV1ToV2Book,
  convertV1CategoryToTag,
  convertV1ToV2Data
}
