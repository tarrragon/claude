/**
 * format-version-detector 單元測試
 *
 * 涵蓋 JSON 版本偵測（5 種情境）和 CSV 版本偵測（3 種情境），
 * 加上邊界輸入安全處理。
 */

const { detectFormatVersion, detectCsvFormatVersion } =
  require('../../../src/export/format-version-detector')

describe('detectFormatVersion', () => {
  // 場景 1: v2 明確版本號偵測
  test('回傳 v2 當 metadata.formatVersion 以 "2." 開頭', () => {
    const data = {
      metadata: { formatVersion: '2.0.0' },
      books: []
    }
    expect(detectFormatVersion(data)).toBe('v2')
  })

  // 場景 2: v2 隱含偵測（有 metadata + readingStatus）
  test('回傳 v2 當 metadata 存在且 books 含 readingStatus 欄位', () => {
    const data = {
      metadata: { exportDate: '2026-01-01' },
      books: [
        { id: 'b1', title: 'Test', readingStatus: 'reading' }
      ]
    }
    expect(detectFormatVersion(data)).toBe('v2')
  })

  // 場景 3: v1 純陣列格式
  test('回傳 v1 當資料為純陣列', () => {
    const data = [
      { id: 'b1', title: 'Test', isNew: true }
    ]
    expect(detectFormatVersion(data)).toBe('v1')
  })

  // 場景 4: v1 含 metadata 包裝但無 formatVersion
  test('回傳 v1 當 data.books 是陣列但無 metadata.formatVersion', () => {
    const data = {
      books: [
        { id: 'b1', title: 'Test', isFinished: true }
      ]
    }
    expect(detectFormatVersion(data)).toBe('v1')
  })

  // 場景 5: 無法辨識的格式
  test('回傳 null 當資料為字串', () => {
    expect(detectFormatVersion('hello')).toBe(null)
  })

  test('回傳 null 當資料為數字', () => {
    expect(detectFormatVersion(123)).toBe(null)
  })

  test('回傳 null 當資料為 null', () => {
    expect(detectFormatVersion(null)).toBe(null)
  })

  test('回傳 null 當資料為 undefined', () => {
    expect(detectFormatVersion(undefined)).toBe(null)
  })

  test('回傳 null 當物件不含 books 屬性', () => {
    expect(detectFormatVersion({ name: 'test' })).toBe(null)
  })
})

describe('detectCsvFormatVersion', () => {
  // 場景 6: CSV v2 偵測
  test('回傳 v2 當 headers 含 readingStatus', () => {
    const headers = ['id', 'title', 'readingStatus', 'progress']
    expect(detectCsvFormatVersion(headers)).toBe('v2')
  })

  // 場景 7: CSV v1 偵測
  test('回傳 v1 當 headers 含 isFinished 但不含 readingStatus', () => {
    const headers = ['id', 'title', 'isFinished', 'progress']
    expect(detectCsvFormatVersion(headers)).toBe('v1')
  })

  test('回傳 v1 當 headers 含 isNew 但不含 readingStatus', () => {
    const headers = ['id', 'title', 'isNew', 'progress']
    expect(detectCsvFormatVersion(headers)).toBe('v1')
  })

  // 場景 8: CSV 降級為 v1
  test('回傳 v1 當 headers 不含任何版本識別欄位', () => {
    const headers = ['id', 'title', 'author']
    expect(detectCsvFormatVersion(headers)).toBe('v1')
  })

  // 邊界：空陣列
  test('回傳 v1 當 headers 為空陣列', () => {
    expect(detectCsvFormatVersion([])).toBe('v1')
  })

  // 邊界：null 輸入
  test('回傳 v1 當 headers 為 null', () => {
    expect(detectCsvFormatVersion(null)).toBe('v1')
  })
})
