---
id: PC-BAL-041
title: 共享 working tree 上編輯即時生效工具源碼的裸露中間態
status: active
severity: high
---

# PC-BAL-041: 共享 working tree 上編輯即時生效工具源碼的裸露中間態

## 基本資訊

- **類別**: process-compliance
- **風險等級**: high
- **發現日期**: 2026-08-18
- **關聯案例**: 同一 session 兩例——lease 模組（import 先改、呼叫點批次改名滯後）與 registry 模組（呼叫已寫、import 未跟上），皆為 multi-PM 協調層施工期間

## 症狀

並行執行體呼叫共用 CLI（如 ticket 指令）時，在核心操作成功後緊接 NameError / ImportError 崩潰；崩潰點位於另一執行體正在編輯、尚未 commit 的模組。exit code 非 0 可能誤導呼叫端判定整個操作失敗而重試或放棄，實際上主狀態已寫入。

## 根因

三個條件疊加：(1) 工具採 cwd-resolving 即時生效機制（每次執行跑當前源碼，無安裝版本緩衝）；(2) 多執行體共享同一 working tree；(3) 編輯者把「改 import」與「改呼叫點」拆在不同 Edit 之間，或任何使模組暫時不可 import 的跨 edit 序列。三者同時成立時，編輯者的每個不一致中間態都即時暴露給全部並行執行體——暴露面還會沿模組載入鏈放大（CLI → lease → registry，編輯深層模組會影響所有上游命令）。

## 解決方案

事發時：令編輯者最優先恢復模組可 import（補 import 或完成替換），以 smoke import + 相關單測驗證後通知其他執行體解除迴避；已崩潰的呼叫端以查詢命令核對主狀態實際結果，勿盲目重試。

## 預防措施

1. **原子替換節奏（強制）**：import 變更與其呼叫點變更必須在同一個 Edit 完成；任何跨 edit 的施工序列，每個中間態都必須通過 smoke import（模組可載入）才可進入下一步。以「測試綠燈或 smoke 通過」為可停中繼點。
2. **派發 prompt 必含此條款**：觸及即時生效工具源碼（CLI 套件、hook 共用 lib）的派發，prompt 明文要求上述節奏。
3. **升級 trigger**：同型事故第三例出現時，將「編輯即時生效工具源碼的 IMP」升級為 worktree 強制隔離（隔離後主 tree 源碼不受在途編輯影響，換取 merge-back 成本）。
4. **不採 shim pin**：版本釘住機制與 cwd-resolving 即時生效的核心價值（改動零安裝生效）直接衝突，複雜度不成比例。

## 相關

- 落地規則：`.claude/pm-rules/parallel-dispatch.md`「即時生效工具源碼的共享樹編輯紀律」節
- 隔離策略評估全文：本專案 worklog 的 multi-PM 協調層實作波 ANA（含兩例第一手序列）
