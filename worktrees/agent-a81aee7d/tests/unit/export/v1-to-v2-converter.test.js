/**
 * v1-to-v2-converter 單元測試
 *
 * 涵蓋書籍轉換（場景 9-12）、category 轉換（場景 13-15）、
 * 完整資料轉換、以及錯誤處理。
 */

const { BookValidationError } = require('../../../src/core/errors/BookValidationError')
const {
  convertV1ToV2Book,
  convertV1CategoryToTag,
  convertV1ToV2Data
} = require('../../../src/export/v1-to-v2-converter')

const FIXED_TIMESTAMP = '2026-04-05T00:00:00.000Z'

describe('convertV1ToV2Book', () => {
  // 場景 9: 標準 v1 書籍轉換
  test('將 v1 完成書籍轉換為 v2 格式', () => {
    const v1Book = {
      id: 'b1',
      title: '三體',
      author: '劉慈欣',
      isFinished: true,
      progress: 100
    }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)

    expect(result.id).toBe('b1')
    expect(result.title).toBe('三體')
    expect(result.authors).toEqual(['劉慈欣'])
    expect(result.readingStatus).toBe('finished')
    expect(result.progress).toBe(100)
    expect(result.tagIds).toEqual([])
    expect(result.isManualStatus).toBe(false)
    expect(result.updatedAt).toBe(FIXED_TIMESTAMP)
    expect(result.source).toBe('readmoo')
    // 不包含 v1 欄位
    expect(result).not.toHaveProperty('isNew')
    expect(result).not.toHaveProperty('isFinished')
    expect(result).not.toHaveProperty('category')
  })

  // 場景 10: v1 書籍 author 為空
  test('author 為空字串時 authors 為空陣列', () => {
    const v1Book = { id: 'b2', title: 'Test', author: '' }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result.authors).toEqual([])
  })

  test('author 為 undefined 時 authors 為空陣列', () => {
    const v1Book = { id: 'b3', title: 'Test' }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result.authors).toEqual([])
  })

  // 場景 11: v1 書籍 progress 為異常值
  test('progress 為字串 "75" 時正規化為 75', () => {
    const v1Book = { id: 'b4', title: 'Test', progress: '75' }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result.progress).toBe(75)
  })

  test('progress 超過 100 時 clamp 為 100', () => {
    const v1Book = { id: 'b5', title: 'Test', progress: 150 }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result.progress).toBe(100)
  })

  test('progress 為 null 時正規化為 0', () => {
    const v1Book = { id: 'b6', title: 'Test', progress: null }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result.progress).toBe(0)
  })

  // 場景 12: v1 書籍含 category 欄位
  test('含 category 時保留為 _v1Category 暫存欄位', () => {
    const v1Book = { id: 'b7', title: 'Test', category: '科幻小說' }
    const result = convertV1ToV2Book(v1Book, FIXED_TIMESTAMP)
    expect(result._v1Category).toBe('科幻小說')
    expect(result).not.toHaveProperty('category')
  })

  // 錯誤處理
  test('輸入為 null 時拋出 BookValidationError', () => {
    expect(() => convertV1ToV2Book(null)).toThrow(BookValidationError)
  })

  test('缺少 id 和 title 時拋出 BookValidationError', () => {
    expect(() => convertV1ToV2Book({})).toThrow(BookValidationError)
  })
})

describe('convertV1CategoryToTag', () => {
  // 場景 13: 正常 category 轉換
  test('建立 TagCategory 和對應的 Tags', () => {
    const result = convertV1CategoryToTag(['科幻', '文學'], FIXED_TIMESTAMP)

    expect(result.tagCategory).not.toBeNull()
    expect(result.tagCategory.id).toBe('cat_imported')
    expect(result.tagCategory.name).toBe('匯入分類')
    expect(result.tags).toHaveLength(2)
    expect(result.tags[0].name).toBe('科幻')
    expect(result.tags[1].name).toBe('文學')
    expect(result.tags[0].categoryId).toBe('cat_imported')
    expect(result.categoryToTagIdMap.size).toBe(2)
    expect(result.categoryToTagIdMap.has('科幻')).toBe(true)
    expect(result.categoryToTagIdMap.has('文學')).toBe(true)
  })

  // 場景 14: category 含空值和「未分類」
  test('跳過空字串和「未分類」', () => {
    const result = convertV1CategoryToTag(
      ['科幻', '', '未分類', '文學'],
      FIXED_TIMESTAMP
    )

    expect(result.tags).toHaveLength(2)
    expect(result.tags[0].name).toBe('科幻')
    expect(result.tags[1].name).toBe('文學')
    expect(result.categoryToTagIdMap.size).toBe(2)
  })

  // 場景 15: 空 category 陣列
  test('空陣列回傳 tagCategory 為 null', () => {
    const result = convertV1CategoryToTag([], FIXED_TIMESTAMP)

    expect(result.tagCategory).toBeNull()
    expect(result.tags).toEqual([])
    expect(result.categoryToTagIdMap.size).toBe(0)
  })
})

describe('convertV1ToV2Data', () => {
  test('完整轉換 v1 純陣列資料為 v2 interchange format', () => {
    const v1Data = [
      { id: 'b1', title: '三體', author: '劉慈欣', isFinished: true, progress: 100, category: '科幻' },
      { id: 'b2', title: '人間失格', author: '太宰治', isNew: true, progress: 0, category: '文學' }
    ]

    const result = convertV1ToV2Data(v1Data)

    expect(result.metadata.formatVersion).toBe('2.0.0')
    expect(result.metadata.totalBooks).toBe(2)
    expect(result.metadata.totalTags).toBe(2)
    expect(result.books).toHaveLength(2)
    expect(result.books[0].readingStatus).toBe('finished')
    expect(result.books[1].readingStatus).toBe('unread')
    // 書籍的 tagIds 已填入
    expect(result.books[0].tagIds).toHaveLength(1)
    expect(result.books[1].tagIds).toHaveLength(1)
    // _v1Category 已移除
    expect(result.books[0]).not.toHaveProperty('_v1Category')
    expect(result.books[1]).not.toHaveProperty('_v1Category')
    // tag 結構正確
    expect(result.tagCategories).toHaveLength(1)
    expect(result.tags).toHaveLength(2)
  })

  test('單本書轉換失敗不中斷整體', () => {
    const v1Data = [
      { id: 'b1', title: '正常書籍', progress: 50 },
      {}, // 缺少 id/title，會失敗
      { id: 'b3', title: '另一本正常書', progress: 0 }
    ]

    const result = convertV1ToV2Data(v1Data)

    expect(result.books).toHaveLength(2)
    expect(result.metadata.totalBooks).toBe(2)
  })

  test('空書籍陣列回傳有效的 v2 結構', () => {
    const result = convertV1ToV2Data([])

    expect(result.metadata.formatVersion).toBe('2.0.0')
    expect(result.metadata.totalBooks).toBe(0)
    expect(result.books).toEqual([])
    expect(result.tagCategories).toEqual([])
    expect(result.tags).toEqual([])
  })
})
