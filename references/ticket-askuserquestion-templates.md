# Ticket 互動場景 AskUserQuestion 模板

本文件提供 PM 在 Ticket 生命週期中使用 AskUserQuestion 工具的標準模板。
場景編號與 askuserquestion-rules.md 場景 #1-#17 完全對應。

> 規範來源：.claude/rules/core/askuserquestion-rules.md（Source of Truth）
> 決策樹定義：.claude/rules/core/decision-tree.md
> 場景詳細說明：.claude/references/askuserquestion-scene-details.md

---

## 場景 #1：驗收方式確認

**觸發條件**：PM 準備 complete 一個 Ticket 前（acceptance-gate-hook 觸發）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "Ticket {ticket_id} 準備完成。選擇驗收方式？",
    "header": "驗收方式",
    "options": [
      {
        "label": "標準驗收 (Recommended)",
        "description": "派發 acceptance-auditor 執行完整驗收"
      },
      {
        "label": "簡化驗收",
        "description": "DOC 類型或任務範圍單純，僅結構完整性檢查"
      },
      {
        "label": "先完成後補驗收",
        "description": "P0 緊急任務，24 小時內補驗收"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項說明**：
- 預設推薦「標準驗收」
- DOC 類型或認知負擔 < 5 時可選「簡化驗收」
- 僅 P0 緊急任務可選「先完成後補驗收」

---

## 場景 #2：Complete 後下一步

**觸發條件**：Ticket 完成且有多個可能的下一步（acceptance-gate-hook 觸發）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "{ticket_id} 已完成。選擇下一步行動？",
    "header": "下一步",
    "options": [
      {
        "label": "開始 {next_id_1}",
        "description": "{next_title_1}（阻塞已解除）"
      },
      {
        "label": "開始 {next_id_2}",
        "description": "{next_title_2}（同 Wave pending）"
      },
      {
        "label": "結束當前 Wave",
        "description": "所有 W{n} 任務已完成或無更多 pending"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- 從待處理任務清單中取前 2-3 個（阻塞已解除優先）
- 加上「結束當前 Wave」或「Handoff 到父任務」作為結束選項
- 若只有 1 個建議，仍使用 AskUserQuestion（提供確認機會）

---

## 場景 #3：Wave/任務收尾確認

**觸發條件**：當前 Wave 無 pending Ticket（情境 C1：版本仍有其他 Wave pending）

**收尾前步驟**（必須先執行）：
1. 列出本次修改的檔案清單
2. 告知 git 未提交狀態（有/無未提交變更）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "W{n} 全部完成。有 {count} 個檔案未提交，版本尚有待處理 Wave。如何收尾？",
    "header": "收尾",
    "options": [
      {
        "label": "提交變更 (Recommended)",
        "description": "git commit 本次 W{n} 的所有修改"
      },
      {
        "label": "查看待處理 Ticket",
        "description": "列出同版本 pending/in_progress Ticket 清單"
      },
      {
        "label": "結束",
        "description": "不提交，稍後處理"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 場景 #4：方案選擇

**觸發條件**：用戶提問包含方案選擇關鍵字，或面臨 3+ 個技術方案

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "有多個技術方案可選。請選擇要採用的方向？",
    "header": "方案選擇",
    "options": [
      {
        "label": "方案 A (Recommended)",
        "description": "{方案A 說明、優缺點}"
      },
      {
        "label": "方案 B",
        "description": "{方案B 說明、優缺點}"
      },
      {
        "label": "方案 C",
        "description": "{方案C 說明、優缺點}"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- 推薦選項放第一位（系統評估或 SA 建議的方案）
- description 說明每個方案的關鍵優缺點
- 最多 4 個選項（AskUserQuestion 限制）

---

## 場景 #5：優先級確認

**觸發條件**：多任務排序，需要用戶決定優先處理順序

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "有多個待處理任務。優先處理哪個？",
    "header": "優先級",
    "options": [
      {
        "label": "{task_id_1} (Recommended)",
        "description": "{task_title_1}（阻塞已解除 / 優先級 P0）"
      },
      {
        "label": "{task_id_2}",
        "description": "{task_title_2}（優先級 P1）"
      },
      {
        "label": "{task_id_3}",
        "description": "{task_title_3}（優先級 P2）"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- 阻塞已解除的任務優先推薦
- 按優先級（P0 > P1 > P2）排序
- 最多展示 3-4 個選項

---

## 場景 #6：任務拆分確認

**觸發條件**：建立 Ticket 時認知負擔 > 10

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "任務認知負擔指數為 {score}（> 10）。如何處理？",
    "header": "拆分",
    "options": [
      {
        "label": "拆分子任務 (Recommended)",
        "description": "按架構層/功能模組拆分為多個子 Ticket"
      },
      {
        "label": "不拆分",
        "description": "直接派發執行（適用於經驗豐富的代理人）"
      },
      {
        "label": "派發 SA 評估",
        "description": "先讓 system-analyst 分析再決定"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 場景 #7：派發方式選擇

**觸發條件**：多任務派發（Task prompt 包含 2+ 個 Ticket ID）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "有 {count} 個任務待派發。選擇派發方式？",
    "header": "派發方式",
    "options": [
      {
        "label": "Task subagent 並行 (Recommended)",
        "description": "各 Agent 獨立完成，不互相影響，最快速"
      },
      {
        "label": "Agent Teams",
        "description": "Agent A 的發現會改變 Agent B 的工作，需即時協商"
      },
      {
        "label": "序列派發",
        "description": "有依賴關係，需按順序執行"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項選擇判斷**：
- 任務無相互依賴 → Task subagent 並行（Recommended）
- A 的發現會影響 B → Agent Teams（成本 3-4x）
- 有明確先後依賴 → 序列派發

---

## 場景 #8：執行方向確認

**觸發條件**：並行/序列、先後順序需要用戶確認

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "{context_description}。確認執行方向？",
    "header": "執行方向",
    "options": [
      {
        "label": "{direction_1} (Recommended)",
        "description": "{direction_1 的說明和影響}"
      },
      {
        "label": "{direction_2}",
        "description": "{direction_2 的說明和影響}"
      }
    ],
    "multiSelect": false
  }]
}
```

**注意**：場景 #8 目前無 Hook 自動提醒，依賴 PM 遵循本規則文件。

---

## 場景 #9：Handoff 方向選擇

**觸發條件**：Ticket 完成後有多個兄弟/子任務可選

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "Ticket {current_id} 已完成。接下來要處理哪個任務？",
    "header": "Handoff",
    "options": [
      {
        "label": "{sibling_id_1} (Recommended)",
        "description": "{sibling_title_1}（阻塞已解除）"
      },
      {
        "label": "{sibling_id_2}",
        "description": "{sibling_title_2}（同 Wave pending）"
      },
      {
        "label": "返回父任務",
        "description": "Handoff 到 {parent_id} - {parent_title}"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- 優先放「阻塞已解除」的 Ticket（加 Recommended）
- 其次放同 Wave 的 pending Ticket
- 最後放「返回父任務」選項
- 最多 3 個選項（超過時選前 2 個 + 父任務）

---

## 場景 #10：開始/收尾確認

**觸發條件**：確認是否開始執行某任務或進入某流程

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "確認是否開始執行？",
    "header": "確認",
    "options": [
      {
        "label": "開始執行 (Recommended)",
        "description": "立即開始 {task_description}"
      },
      {
        "label": "稍後執行",
        "description": "先完成其他前置工作"
      }
    ],
    "multiSelect": false
  }]
}
```

**注意**：場景 #10 目前無 Hook 自動提醒，依賴 PM 遵循本規則文件。

---

## 使用原則

### 何時使用 AskUserQuestion

| 條件 | 使用 |
|------|------|
| 有 2+ 個可選方向 | 必須使用 |
| 只有 1 個明確方向 | 仍建議使用（提供確認機會） |
| 自動判斷結果明確 | 可跳過（如自動 handoff） |

### 何時不使用

| 條件 | 原因 |
|------|------|
| Hook 自動執行的檢查 | 不涉及使用者決策 |
| 單一方向無歧義 | 自動執行即可 |
| 純資訊性提醒 | 不需要使用者回答 |

### 選項設計原則

1. **選項數量**：2-4 個（AskUserQuestion 限制）
2. **推薦標記**：系統推薦的選項加 `(Recommended)` 後綴
3. **描述清晰**：每個選項的 description 說明選擇的後果
4. **動態生成**：Ticket ID 和標題從系統資料動態填入

---

## 場景 #11：Commit 後情境感知 Handoff

**觸發條件**：每次 git commit 成功後（commit-handoff-hook 觸發）

**重要**：#16 必須在 #11 之前執行（Checkpoint 1.5 → Checkpoint 2）

**#11a：Context 刷新**（情境 A — ticket 仍 in_progress）

```json
{
  "questions": [{
    "question": "本次 session 已完成：\n- {已完成項目}\n- commit: {hash} {message}\n\n此 ticket 仍在進行中。接下來要？",
    "header": "Handoff",
    "options": [
      {
        "label": "Handoff (Context 刷新)（Recommended）",
        "description": "在新 session 以乾淨 context 繼續同一 ticket"
      },
      {
        "label": "繼續在此 session 工作",
        "description": "留在當前 context 繼續"
      },
      {
        "label": "/clear 結束 session",
        "description": "清空對話，不建立 handoff 檔案"
      }
    ],
    "multiSelect": false
  }]
}
```

**#11b：任務切換**（情境 B — ticket 已 completed，有關聯任務）

```json
{
  "questions": [{
    "question": "本次 session 已完成：\n- {已完成項目}\n- commit: {hash} {message}\n\nTicket 已完成。切換到下一個任務嗎？",
    "header": "Handoff",
    "options": [
      {
        "label": "Handoff 到 {next_ticket_id}（Recommended）",
        "description": "在新 session 切換到下一個 ticket"
      },
      {
        "label": "在此 session 繼續 {next_ticket_id}",
        "description": "直接 claim，留在當前 context"
      },
      {
        "label": "查看所有待處理任務後決定",
        "description": "列出後讓用戶選擇"
      },
      {
        "label": "/clear 結束 session",
        "description": "清空對話，不建立 handoff 檔案"
      }
    ],
    "multiSelect": false
  }]
}
```

**核心原則**：Handoff 永遠是第一選項且標記 (Recommended)；繼續在此 session 工作是例外，不是預設。

---

## 場景 #12：流程省略確認

**觸發條件**：Hook 偵測到省略意圖關鍵字（process-skip-guard-hook 觸發）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "偵測到流程省略意圖：{skip_description}。確認如何處理？",
    "header": "省略確認",
    "options": [
      {
        "label": "不省略 (Recommended)",
        "description": "執行完整流程：{full_process}"
      },
      {
        "label": "確認省略",
        "description": "用戶明確同意省略此步驟"
      },
      {
        "label": "簡化執行",
        "description": "執行精簡版本的流程"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- `{skip_description}` 從 Hook 偵測到的省略類別動態填入
- `{full_process}` 從省略類別對應的完整流程描述填入

---

## 場景 #13：後續任務路由確認

**觸發條件**：任務/階段完成後有多個後續路由（phase-completion-gate-hook 觸發）

**AskUserQuestion 配置（Phase 3b 完成範例）**：

```json
{
  "questions": [{
    "question": "Phase 3b 已完成。選擇後續路由？",
    "header": "路由",
    "options": [
      {
        "label": "/parallel-evaluation B (Recommended)",
        "description": "啟動多視角重構分析（Redundancy, Coupling, Complexity）"
      },
      {
        "label": "直接進入 Phase 4b",
        "description": "豁免：<=2 檔案/DOC 類型/任務範圍單純"
      },
      {
        "label": "先 commit 再決定",
        "description": "提交當前變更後再選擇路由"
      }
    ],
    "multiSelect": false
  }]
}
```

**選項生成規則**：
- 選項依 task_type 動態變化（分析完成/規劃完成/Phase 3b/Phase 4/incident）
- 推薦選項根據完成階段自動標記 Recommended

---

## 場景 #14：parallel-evaluation 觸發確認

**觸發條件**：階段完成後系統建議可用 parallel-evaluation（phase-completion-gate-hook 觸發）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "建議執行 /parallel-evaluation 情境 {scenario}（{scenario_name}）。是否執行？",
    "header": "評估",
    "options": [
      {
        "label": "執行 (Recommended)",
        "description": "啟動多視角掃描：{perspectives}"
      },
      {
        "label": "跳過",
        "description": "直接進入下一步（會觸發省略確認）"
      },
      {
        "label": "執行其他情境",
        "description": "選擇不同的 parallel-evaluation 情境"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 場景 #15：Bulk 變更前備份確認

**觸發條件**：即將進行批量修改（parallel-suggestion-hook 觸發）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "即將進行批量修改。是否先建立回退點？",
    "header": "備份",
    "options": [
      {
        "label": "先 commit 備份 (Recommended)",
        "description": "建立回退點，確保可安全回滾"
      },
      {
        "label": "直接開始",
        "description": "不備份，直接進行修改"
      },
      {
        "label": "查看變更範圍",
        "description": "先確認將修改的檔案清單後再決定"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 場景 #16：錯誤學習經驗確認

**觸發條件**：git commit 成功後（commit-handoff-hook 觸發）；docs:/chore:/style:/refactor:/test: 前綴 commit 自動跳過

**執行順序**：#16 → #11（Checkpoint 1.5 → Checkpoint 2，不可跳過或顛倒）

**AskUserQuestion 配置**（二元確認）：

```json
{
  "questions": [{
    "question": "本次 commit 是否有需要記錄的錯誤學習經驗？（例如：踩到的坑、發現的反模式、設計決策教訓）",
    "header": "錯誤學習",
    "options": [
      {
        "label": "無 (Recommended)",
        "description": "本次 commit 無特殊錯誤經驗"
      },
      {
        "label": "有，執行 /error-pattern add",
        "description": "記錄本次發現的模式"
      }
    ],
    "multiSelect": false
  }]
}
```

**選擇「有」後的流程**：
1. 執行 /error-pattern add
2. 記錄完成後回到 Checkpoint 1.5（再次確認）
3. 選擇「無」後進入 #11

---

## 場景 #17：錯誤經驗改進追蹤

**觸發條件**：`ticket track complete` 時，ticket 執行期間有新增 error-pattern（acceptance-gate-hook 觸發）

**執行順序**：complete 先執行，#17 在 complete 後處理（避免死鎖）

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "本 ticket 執行期間新增了 {N} 個錯誤學習經驗：\n- {pattern_id}: {pattern_title}\n\n這些錯誤經驗是否需要建立改進 Ticket？",
    "header": "錯誤改進",
    "options": [
      {
        "label": "建立改進 Ticket (Recommended)",
        "description": "為新增的 error-pattern 建立修復/防護 Ticket"
      },
      {
        "label": "已有對應 Ticket",
        "description": "error-pattern 相關修復已在現有 Ticket 中"
      },
      {
        "label": "延後處理",
        "description": "記錄到 todolist.yaml，後續版本排程"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 相關文件

- .claude/rules/core/askuserquestion-rules.md - AskUserQuestion 規則（Source of Truth，場景 #1-#17）
- .claude/references/askuserquestion-scene-details.md - 各場景詳細說明
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期（互動規範定義）
- .claude/rules/core/decision-tree.md - 決策樹（AskUserQuestion 強制場景）
- .claude/skills/ticket/SKILL.md - Ticket 系統使用指南
- .claude/skills/parallel-evaluation/SKILL.md - parallel-evaluation 工具

---

**Last Updated**: 2026-03-09
**Version**: 3.0.0 - 修復場景編號系統：統一使用規則 #1-#17 編號（W22-011），補充缺失場景 #4/#5/#7/#8/#10/#16/#17
**Source**: 0.31.0-W28-033, W22-011
