# PC-030: 代理人定義中使用 slash command 引用 Skill，但代理人無法觸發 slash command

**發現日期**: 2026-03-27
**相關 Ticket**: 0.2.0-W7-011

## 症狀

- 代理人定義（如 lavender）中寫著「執行 `/spec init {ticket-id}`」
- 代理人被派發後，這些 slash command 指令永遠不會被執行
- Skill 工具（`/spec`、`/ticket`、`/pre-fix-eval` 等）只有主線程能觸發
- 代理人定義中的 slash command 引用形同死文件，設計意圖無法實現

## 根因

1. **平台機制誤解**：Skill tool 是 Claude Code 主線程（用戶對話介面）的專屬功能，subagent 的工具清單中沒有 Skill tool
2. **撰寫慣性**：在主線程撰寫代理人定義時，習慣使用自己熟悉的 slash command 語法，未考慮代理人的實際可用工具
3. **缺乏驗證機制**：無 Hook 或 lint 規則檢查代理人定義中是否包含無法執行的 slash command

## 解決方案

代理人定義中引用 Skill 時，必須改為 Read 對應的 SKILL.md 檔案路徑：

| 錯誤寫法 | 正確寫法 |
|---------|---------|
| `執行 /spec init` | `依 .claude/skills/spec/SKILL.md init 流程` |
| `使用 /ticket create` | `使用 ticket create CLI 指令（透過 Bash 工具）` |
| `/search-tools-guide 或閱讀 SKILL.md` | 直接引用 `.claude/skills/search-tools-guide/SKILL.md` |

## 預防措施

1. **撰寫代理人定義時**：Skill 引用一律使用 `Read .claude/skills/{name}/SKILL.md` 格式，不使用 slash command
2. **Review 檢查項目**：代理人定義中出現 `` `/xxx` `` 格式時，確認是否為代理人可執行的操作
3. **CLI 工具（ticket 等）**：代理人可透過 Bash 工具直接執行已安裝的 CLI（如 `ticket create`），不需要 slash command

## 行為模式分析

此錯誤屬於「撰寫者視角 vs 執行者視角不一致」模式：

| 角色 | 可用工具 | Skill 存取方式 |
|------|---------|---------------|
| 主線程（PM） | Skill tool、Bash、Read 等全部 | `/spec init`（slash command） |
| Subagent（代理人） | 定義中指定的工具（無 Skill tool） | `Read .claude/skills/spec/SKILL.md` |

> **核心教訓**：撰寫代理人定義時，必須從代理人的視角檢查每個指令是否可執行。代理人的工具清單是有限的，不能假設它擁有與主線程相同的能力。
