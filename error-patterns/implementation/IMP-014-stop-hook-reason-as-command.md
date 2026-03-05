# IMP-014: Stop Hook reason 欄位被 Claude 解讀為命令

## 分類
- **類型**: implementation
- **嚴重度**: 中
- **發現版本**: v0.3.0
- **發現日期**: 2026-03-05

## 模式描述

Stop hook 回傳 `{"decision": "block", "reason": "/ticket resume {id}"}` 時，
Claude Code 將 `reason` 文字注入為下一輪對話的 context/指令，Claude 把它當作斜線命令執行，
導致 handoff 後不等待用戶 `/clear` 就自動執行 resume。

## 具體案例

**症狀**：
- 執行 `/ticket handoff` 後，Stop hook 被觸發
- Claude 未等待用戶執行 `/clear`，直接自動執行 `/ticket resume {id}`
- 用戶看到 `Stop hook error: /ticket resume 0.3.0-W1-001`

**根因**：
Claude Code Stop hook 的 `block` decision 中，`reason` 欄位不是給用戶看的文字，
而是被 Claude Code 注入為新一輪 context 讓 Claude 繼續回應。
當 `reason` 包含 `/ticket resume {id}` 這樣的文字，Claude 將其解讀為用戶命令並執行。

**位置**：`.claude/hooks/handoff-auto-resume-stop-hook.py` 第 577-584 行（v2.2.0）

**舊版錯誤設計**：
```python
return {
    "decision": "block",
    "reason": f"/ticket resume {ticket_id}"  # 看起來像命令，Claude 會執行
}
```

**修復後設計**（v2.3.0）：
```python
return {
    "decision": "block",
    "reason": (
        f"[Handoff] 偵測到未完成的 handoff 任務：{ticket_id}\n"
        f"請告知用戶：先執行 /clear 清空 context，"
        f"然後再執行 /ticket resume {ticket_id} 恢復任務。\n"
        f"請勿自動執行 resume，必須等待用戶手動操作。"
    )
}
```

**修復 commit**：`78c974d`

## 根本機制

| Hook decision | Claude Code 行為 | 備註 |
|--------------|-----------------|------|
| `{"suppressOutput": true}` | 靜默通過，對話終止 | 正常結束 |
| `{"decision": "block", "reason": "..."}` | 阻止對話終止，將 reason 注入為新 context | Claude 會回應 reason 的內容 |

`reason` 欄位的作用類似「新的 user message」，Claude 會根據它的內容採取行動。

## 防護措施

### 設計 Stop hook 的 block reason 時
- [ ] reason 文字必須是**說明性文字**，不能包含可執行的命令
- [ ] 若需要提示用戶執行某命令，使用「請告知用戶執行 XXX」的語法
- [ ] 明確在 reason 中加入「請勿自動執行」的指示
- [ ] 避免 reason 文字以 `/` 開頭或包含指令語法

### 設計其他 Hook 的 reason/message 時
- [ ] 同樣注意：任何被注入為 context 的文字都可能被 Claude 解讀為指令
- [ ] 使用描述性語言而非命令式語言

## 適用範圍

不僅限於 Stop hook，所有會將輸出注入為 Claude context 的 Hook 都適用：
- Stop hook 的 `reason` 欄位（`decision: block`）
- PreToolUse hook 的 `reason` 欄位（`decision: block`）

## 相關錯誤模式
- IMP-006 案例 D: Hook 非成功路徑遺漏 stderr 輸出（同屬 Hook 輸出設計缺陷）

## 相關文件
- `.claude/hooks/handoff-auto-resume-stop-hook.py` - 修復位置
