# Cross-Reviewer Convergence 是優先序訊號

> **角色**：本卡是 `multi-round-review` 的支撐型原則、被「整合 finding 工作流」段引用。
>
> **何時讀**：整合多個 reviewer 的 finding 排優先序時。

## 結論

同一輪內、多個 reviewer 獨立 catch 出同一個 finding 是「真議題」的強訊號。Convergence 越高、優先序越高、修法價值越明確。

## 三層 convergence

| 層級                | 訊號                                             | 優先序         |
| ------------------- | ------------------------------------------------ | -------------- |
| 跨 reviewer 收斂    | 同輪 3 個 reviewer 中 2+ 個獨立 catch 同 finding | 立即修         |
| 跨輪收斂            | Round N+1 用新 frame 仍 catch 出類似 finding     | 立即修         |
| 單一 reviewer catch | 只有 1 個 reviewer catch                         | 建議修但非阻塞 |

## 為什麼 convergence 是優先序訊號

- **獨立性降低 bias**：不同 reviewer 受不同 frame / instance / 寫法影響、convergence 排除了「特定 reviewer 偏好」
- **真議題會在多軸出現**：systemic 違規通常在多個 surface / scope 都浮現、所以多 frame 都會 catch
- **修法 ROI 高**：cross-reviewer 收斂的 finding 通常是 systemic、修一處能消除多種症狀

## 反模式

- 「最嚴格的 reviewer 列為 priority」— 嚴格不等於 convergence、可能只是該 reviewer 偏好
- 「找出 3 個 reviewer 都不同意的點才修」— 反向誤用、convergence 是「同意有問題」、不是「不同意有問題」
- 跨輪 convergence 沒做：只比較同輪、忽略 Round 1 / 2 / 3 之間有沒有重複 surface 同類問題（重複 = frame 沒切乾淨）

## 整合 finding 的標準動作

1. 收到 N 個 reviewer 報告、用表格列出每個 finding 跟對應 reviewer
2. 標 convergence 等級（cross-reviewer / 單 reviewer）
3. 按 convergence × 嚴重性 排優先序
4. 立即修 = 高 convergence + 高嚴重性
5. Backlog = 低 convergence + 中等嚴重性
6. 不修 = 低 convergence + 低嚴重性 + 修法成本高
