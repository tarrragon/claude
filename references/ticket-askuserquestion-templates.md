# Ticket 互動場景 AskUserQuestion 模板

本文件提供 PM 在 Ticket 生命週期中使用 AskUserQuestion 工具的標準模板。

> 規範來源：.claude/rules/flows/ticket-lifecycle.md（v4.2.0）
> 決策樹定義：.claude/rules/core/decision-tree.md（v5.1.0）
> 分析 Ticket：0.31.0-W23-001

---

## 場景 1：Handoff 方向選擇

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

## 場景 2：Complete 前驗收方式確認

**觸發條件**：PM 準備 complete 一個 Ticket 前

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
        "description": "DOC 類型或認知負擔 < 5，僅結構完整性檢查"
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

## 場景 3：Complete 後下一步選擇

**觸發條件**：Ticket 完成且有多個可能的下一步

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
- 從 `_print_next_steps()` 的建議清單中取前 2-3 個
- 加上「結束當前 Wave」或「Handoff 到父任務」作為結束選項
- 若只有 1 個建議，仍使用 AskUserQuestion（提供確認機會）

---

## 場景 4：任務拆分確認

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

## 場景 5：Wave/任務完成收尾確認

**觸發條件**：Wave 或批次任務全部完成後

**收尾步驟**（AskUserQuestion 前必須先執行）：
1. 列出本次修改的檔案清單
2. 告知 git 未提交狀態（有/無未提交變更）
3. 查詢同版本是否有其他 pending/in_progress Ticket

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "W{n} 全部完成。有 {count} 個檔案未提交，{pending_count} 個待處理 Ticket。如何收尾？",
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

**選項生成規則**：
- 有未提交變更時，推薦「提交變更」
- 有待處理 Ticket 時，description 中顯示數量
- 「結束」選項永遠存在

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

## 場景 6：Commit 後 Handoff 確認（場景 #11）

**觸發條件**：每次 git commit 成功後

**AskUserQuestion 配置**：

```json
{
  "questions": [{
    "question": "Commit 已完成。選擇下一步行動？",
    "header": "Handoff",
    "options": [
      {
        "label": "Handoff (Recommended)",
        "description": "結束當前 context，保持乾淨的工作環境"
      },
      {
        "label": "繼續後續任務",
        "description": "留在當前 context 繼續工作"
      },
      {
        "label": "查看後續任務再決定",
        "description": "先列出可進行的任務後選擇"
      }
    ],
    "multiSelect": false
  }]
}
```

---

## 場景 7：流程省略確認（場景 #12）

**觸發條件**：Hook 偵測到省略意圖關鍵字

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

## 場景 8：後續任務路由確認（場景 #13）

**觸發條件**：任務/階段完成後有多個後續路由

**AskUserQuestion 配置（Phase 3b 完成範例）**：

```json
{
  "questions": [{
    "question": "Phase 3b 已完成。選擇後續路由？",
    "header": "路由",
    "options": [
      {
        "label": "/parallel-evaluation A (Recommended)",
        "description": "啟動程式碼審查（Reuse, Quality, Efficiency 視角）"
      },
      {
        "label": "直接進入 Phase 4",
        "description": "跳過多視角審查，直接重構評估"
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

## 場景 9：parallel-evaluation 觸發確認（場景 #14）

**觸發條件**：階段完成後系統建議可用 parallel-evaluation

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

## 場景 10：Bulk 變更前備份確認（場景 #15）

**觸發條件**：即將進行批量修改

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

## 相關文件

- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期（互動規範定義）
- .claude/rules/core/decision-tree.md - 決策樹（AskUserQuestion 強制場景）
- .claude/rules/core/askuserquestion-rules.md - AskUserQuestion 規則（Source of Truth）
- .claude/skills/ticket/SKILL.md - Ticket 系統使用指南
- .claude/skills/parallel-evaluation/SKILL.md - parallel-evaluation 工具

---

**Last Updated**: 2026-03-02
**Version**: 2.0.0 - 新增場景 6-10（對應規則場景 11-15）
**Source**: 0.31.0-W28-033
