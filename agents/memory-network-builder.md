---
name: memory-network-builder
description: "[DEPRECATED] 已合併到 continuous-learning Skill。記憶捕獲和知識圖譜功能請使用 .claude/skills/continuous-learning/SKILL.md"
model: haiku
---

# memory-network-builder [DEPRECATED]

**狀態**：已棄用（2026-03-02）

**合併目標**：`.claude/skills/continuous-learning/SKILL.md`

**原因**：memory-network-builder 的核心功能（捕獲洞察、建立知識圖譜）與 continuous-learning Skill（提取可復用模式）重疊率 75%。合併後由 continuous-learning 統一處理學習沉澱和記憶捕獲。

**遷移指引**：

| 原功能 | 新位置 |
|--------|--------|
| Session 學習沉澱 | continuous-learning（自動 Stop hook） |
| 原子化記憶建立 | continuous-learning > Memory Capture |
| 記憶格式規範 | continuous-learning/references/memory-capture-guide.md |
| 記憶類型定義 | continuous-learning/references/memory-capture-guide.md |
| 連結策略 | continuous-learning/references/memory-capture-guide.md |

**保留此檔案的原因**：多處歷史文件引用 memory-network-builder，保留 deprecated 標記確保引用可追溯。

---

*Deprecated: 2026-03-02*
*Superseded by: continuous-learning Skill (0.31.0-W28-004)*
