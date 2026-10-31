// shared.ts 的測試：票號前綴與票檔位置、專案設定檔內容的判定、checkout 路徑判定、距今時間、票檔 frontmatter 狀態與 title 解析。

import { describe, expect, test } from 'claude-code/testing'

import { ticketFile } from './fixtures'
import {
  formatAge,
  parseFrontmatterStatus,
  parseFrontmatterTitle,
  parseProjectConfig,
  parseWorktreePaths,
  resolveTicketFile,
  ticketFileCandidates,
  ticketPrefixOf,
} from '../hooks/shared'

describe('ticketFileCandidates', () => {
  test('版本可解析 major.minor：先 hierarchical 再 flat', () => {
    expect(ticketFileCandidates('0.5.0-W1-349')).toEqual([
      'docs/work-logs/v0/v0.5/v0.5.0/tickets/0.5.0-W1-349.md',
      'docs/work-logs/v0.5.0/tickets/0.5.0-W1-349.md',
    ])
    expect(ticketFileCandidates('1.12.3-W20-001.2.1')).toEqual([
      'docs/work-logs/v1/v1.12/v1.12.3/tickets/1.12.3-W20-001.2.1.md',
      'docs/work-logs/v1.12.3/tickets/1.12.3-W20-001.2.1.md',
    ])
  })

  test('版本字串無法解析 major.minor：只有 flat', () => {
    expect(ticketFileCandidates('1-W1-001')).toEqual(['docs/work-logs/v1/tickets/1-W1-001.md'])
  })

  test('不是票號時沒有候選', () => {
    expect(ticketFileCandidates('待定')).toEqual([])
    expect(ticketFileCandidates('W1-001')).toEqual([])
  })
})

describe('resolveTicketFile', () => {
  const hierarchical = 'docs/work-logs/v0/v0.5/v0.5.0/tickets/0.5.0-W1-349.md'
  const flat = 'docs/work-logs/v0.5.0/tickets/0.5.0-W1-349.md'

  test('hierarchical 存在時用之（flat 也存在亦同）', () => {
    expect(resolveTicketFile('0.5.0-W1-349', () => true)).toBe(hierarchical)
    expect(resolveTicketFile('0.5.0-W1-349', path => path === hierarchical)).toBe(hierarchical)
  })

  test('hierarchical 不存在而 flat 存在時退回 flat', () => {
    expect(resolveTicketFile('0.5.0-W1-349', path => path === flat)).toBe(flat)
  })

  test('兩者皆不存在時預設 hierarchical（對齊 paths.py get_tickets_dir_under_root）', () => {
    expect(resolveTicketFile('0.5.0-W1-349', () => false)).toBe(hierarchical)
  })

  test('版本字串無法解析 major.minor 時為 flat；不是票號時為 null', () => {
    expect(resolveTicketFile('1-W1-001', () => false)).toBe('docs/work-logs/v1/tickets/1-W1-001.md')
    expect(resolveTicketFile('待定', () => true)).toBeNull()
  })
})

describe('ticketPrefixOf', () => {
  test('協調票 ID 去掉流水號（含子序號）得短票號前綴', () => {
    expect(ticketPrefixOf('0.5.0-W1-349')).toBe('0.5.0-W1-')
    expect(ticketPrefixOf('0.6.0-W12-007.3.1')).toBe('0.6.0-W12-')
  })

  test('不是票號時回傳 null', () => {
    expect(ticketPrefixOf('349')).toBeNull()
    expect(ticketPrefixOf('0.5.0-W1-')).toBeNull()
  })
})

describe('parseProjectConfig', () => {
  test('coordinationTicket 為完整票號時成立，取其值', () => {
    expect(parseProjectConfig('{ "coordinationTicket": "0.6.0-W2-010" }')).toEqual({
      kind: 'ok',
      coordinationTicket: '0.6.0-W2-010',
    })
  })

  test('JSON 無效時為 invalid-json', () => {
    expect(parseProjectConfig('{ "coordinationTicket": ').kind).toBe('invalid-json')
  })

  test('不是 JSON 物件或缺 coordinationTicket 時為 missing-field', () => {
    expect(parseProjectConfig('{ "otherField": "0.6.0-W2-010" }')).toEqual({ kind: 'missing-field' })
    expect(parseProjectConfig('["0.6.0-W2-010"]')).toEqual({ kind: 'missing-field' })
    expect(parseProjectConfig('null')).toEqual({ kind: 'missing-field' })
  })

  test('coordinationTicket 不是完整票號時為 invalid-format，帶原值', () => {
    expect(parseProjectConfig('{ "coordinationTicket": "010" }')).toEqual({ kind: 'invalid-format', value: '010' })
    expect(parseProjectConfig('{ "coordinationTicket": 10 }')).toEqual({ kind: 'invalid-format', value: 10 })
  })
})

describe('parseWorktreePaths', () => {
  test('取 git worktree list 的所有 checkout，主 checkout 在第一筆', () => {
    const porcelain = [
      'worktree /repo',
      'HEAD aaa',
      'branch refs/heads/main',
      '',
      'worktree /repo/.claude/worktrees/agent-x',
      'HEAD ddd',
      'branch refs/heads/worktree-agent-x',
      'locked claude agent agent-x',
      '',
    ].join('\n')
    expect(parseWorktreePaths(porcelain)).toEqual(['/repo', '/repo/.claude/worktrees/agent-x'])
  })

  test('空輸出回傳空陣列', () => {
    expect(parseWorktreePaths('')).toEqual([])
  })
})

describe('formatAge', () => {
  test('秒、分、小時、天；未來時間為 0 秒；缺少時間為時間不明', () => {
    expect(formatAge(59_000, 0)).toBe('59 秒前')
    expect(formatAge(60_000, 0)).toBe('1 分前')
    expect(formatAge(3 * 3_600_000, 0)).toBe('3 小時前')
    expect(formatAge(2 * 86_400_000, 0)).toBe('2 天前')
    expect(formatAge(0, 5_000)).toBe('0 秒前')
    expect(formatAge(0, null)).toBe('時間不明')
  })
})

describe('parseFrontmatterStatus', () => {
  test('讀 frontmatter 內的 status，不讀本文', () => {
    expect(parseFrontmatterStatus(ticketFile('in_progress'))).toBe('in_progress')
    expect(parseFrontmatterStatus("---\nstatus: 'completed'\n---\n")).toBe('completed')
  })

  test('沒有 frontmatter 或沒有 status 欄時回傳 null', () => {
    expect(parseFrontmatterStatus('status: pending\n')).toBeNull()
    expect(parseFrontmatterStatus('---\nid: x\n---\nstatus: pending\n')).toBeNull()
  })
})

describe('parseFrontmatterTitle', () => {
  test('讀 frontmatter 內的 title，不讀本文；單引號與雙引號包住的值去掉引號', () => {
    expect(parseFrontmatterTitle(ticketFile('pending', '實作 line-board 佇列票摘要'))).toBe('實作 line-board 佇列票摘要')
    expect(parseFrontmatterTitle(ticketFile('pending', "'補上 has_functional_requirements: false 宣告'"))).toBe(
      '補上 has_functional_requirements: false 宣告',
    )
    expect(parseFrontmatterTitle(ticketFile('pending', "'含 ''引號'' 的標題'"))).toBe("含 '引號' 的標題")
    expect(parseFrontmatterTitle(ticketFile('pending', '"雙引號 \\"內含\\" 的標題"'))).toBe('雙引號 "內含" 的標題')
  })

  test('沒有 frontmatter、沒有 title 欄或 title 為空時回傳 null', () => {
    expect(parseFrontmatterTitle('title: x\n')).toBeNull()
    expect(parseFrontmatterTitle(ticketFile('pending'))).toBeNull()
    expect(parseFrontmatterTitle(ticketFile('pending', "''"))).toBeNull()
  })
})
